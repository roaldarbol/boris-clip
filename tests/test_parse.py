# test_parse.py
#
# Tests:
# - Tabular CSV: basic START/STOP pairing produces correct bouts
# - Tabular CSV: POINT events are correctly identified
# - Tabular CSV: unmatched STOP is skipped with a warning
# - Tabular CSV: unclosed START is skipped with a warning
# - Tabular CSV: multiple subjects are handled independently
# - Tabular CSV: media filename is extracted from header
# - Aggregated CSV: start/stop columns produce correct bouts
# - Aggregated CSV: equal start/stop is treated as point event
# - .boris project file: state events are paired correctly
# - .boris project file: point events from ethogram are handled
# - .boris project file: media filename is extracted
# - Format detection: aborts on unrecognised CSV
# - _resolve_padding: --padding sets both sides
# - _resolve_padding: --padding-pre overrides only pre
# - _resolve_padding: --padding-post overrides only post
# - _resolve_padding: both overrides together

import io
import json
import textwrap

import pandas as pd
import pytest

from boris_clip.cli import _resolve_padding, _resolve_point_padding
from boris_clip.models import Bout
from boris_clip.parse import (
    _detect_csv_format,
    _parse_aggregated_csv,
    _parse_tabular_csv,
    _parse_boris_project,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tabular_df(rows: list[dict]) -> pd.DataFrame:
    base = {
        "Time": [],
        "Subject": [],
        "Behavior": [],
        "Status": [],
        "Media file path": [],
        "FPS": [],
        "Total length": [],
    }
    for row in rows:
        for k, v in row.items():
            base.setdefault(k, []).append(v)
        # fill missing keys
        for k in base:
            if k not in row:
                base[k].append(None)
    return pd.DataFrame(base)


def _aggregated_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _boris_project(observations: dict, ethogram: dict | None = None) -> dict:
    return {
        "ethogram": ethogram or {},
        "observations": observations,
    }


# ---------------------------------------------------------------------------
# Tabular CSV
# ---------------------------------------------------------------------------

class TestTabularCSV:
    def test_basic_start_stop(self, tmp_path):
        df = _tabular_df([
            {"Time": 1.0, "Subject": "ind1", "Behavior": "walking", "Status": "START"},
            {"Time": 4.0, "Subject": "ind1", "Behavior": "walking", "Status": "STOP"},
        ])
        result = _parse_tabular_csv(df, tmp_path / "dummy.csv")
        assert len(result.bouts) == 1
        bout = result.bouts[0]
        assert bout.subject == "ind1"
        assert bout.behaviour == "walking"
        assert bout.start == pytest.approx(1.0)
        assert bout.stop == pytest.approx(4.0)
        assert not bout.is_point

    def test_point_event(self, tmp_path):
        df = _tabular_df([
            {"Time": 2.5, "Subject": "ind1", "Behavior": "scratch", "Status": "POINT"},
        ])
        result = _parse_tabular_csv(df, tmp_path / "dummy.csv")
        assert len(result.bouts) == 1
        assert result.bouts[0].is_point
        assert result.bouts[0].start == pytest.approx(2.5)
        assert result.bouts[0].stop == pytest.approx(2.5)

    def test_unmatched_stop_is_skipped(self, tmp_path, recwarn):
        df = _tabular_df([
            {"Time": 5.0, "Subject": "ind1", "Behavior": "walking", "Status": "STOP"},
        ])
        result = _parse_tabular_csv(df, tmp_path / "dummy.csv")
        assert len(result.bouts) == 0

    def test_unclosed_start_is_skipped(self, tmp_path):
        df = _tabular_df([
            {"Time": 1.0, "Subject": "ind1", "Behavior": "walking", "Status": "START"},
        ])
        result = _parse_tabular_csv(df, tmp_path / "dummy.csv")
        assert len(result.bouts) == 0

    def test_multiple_subjects_independent(self, tmp_path):
        df = _tabular_df([
            {"Time": 0.0, "Subject": "A", "Behavior": "run", "Status": "START"},
            {"Time": 1.0, "Subject": "B", "Behavior": "run", "Status": "START"},
            {"Time": 2.0, "Subject": "A", "Behavior": "run", "Status": "STOP"},
            {"Time": 3.0, "Subject": "B", "Behavior": "run", "Status": "STOP"},
        ])
        result = _parse_tabular_csv(df, tmp_path / "dummy.csv")
        assert len(result.bouts) == 2
        starts = {b.subject: b.start for b in result.bouts}
        assert starts["A"] == pytest.approx(0.0)
        assert starts["B"] == pytest.approx(1.0)

    def test_media_filename_extracted(self, tmp_path):
        df = _tabular_df([
            {"Time": 0.0, "Subject": "A", "Behavior": "run", "Status": "START",
             "Media file path": "/data/video.mp4"},
            {"Time": 1.0, "Subject": "A", "Behavior": "run", "Status": "STOP",
             "Media file path": "/data/video.mp4"},
        ])
        result = _parse_tabular_csv(df, tmp_path / "dummy.csv")
        assert result.media_filename == "video.mp4"


# ---------------------------------------------------------------------------
# Aggregated CSV
# ---------------------------------------------------------------------------

class TestAggregatedCSV:
    def test_basic_bout(self, tmp_path):
        df = _aggregated_df([
            {"Subject": "ind1", "Behavior": "grooming", "Start (s)": 10.0, "Stop (s)": 15.5},
        ])
        result = _parse_aggregated_csv(df, tmp_path / "dummy.csv")
        assert len(result.bouts) == 1
        b = result.bouts[0]
        assert b.start == pytest.approx(10.0)
        assert b.stop == pytest.approx(15.5)
        assert not b.is_point

    def test_equal_start_stop_is_point(self, tmp_path):
        df = _aggregated_df([
            {"Subject": "ind1", "Behavior": "vocalise", "Start (s)": 7.0, "Stop (s)": 7.0},
        ])
        result = _parse_aggregated_csv(df, tmp_path / "dummy.csv")
        assert result.bouts[0].is_point


# ---------------------------------------------------------------------------
# .boris project file
# ---------------------------------------------------------------------------

class TestBorisProject:
    def _write_project(self, tmp_path, project: dict) -> str:
        p = tmp_path / "test.boris"
        p.write_text(json.dumps(project), encoding="utf-8")
        return str(p)

    def test_state_event_pairing(self, tmp_path):
        project = _boris_project(
            ethogram={"0": {"name": "walking", "type": "State event"}},
            observations={
                "obs1": {
                    "events": [
                        [1.0, "ind1", "walking", "", ""],
                        [4.0, "ind1", "walking", "", ""],
                    ],
                    "file": {"1": ["/data/video.mp4"]},
                }
            },
        )
        p = self._write_project(tmp_path, project)
        from boris_clip.parse import _parse_boris_project
        result = _parse_boris_project(tmp_path / "test.boris")
        assert len(result.bouts) == 1
        assert result.bouts[0].start == pytest.approx(1.0)
        assert result.bouts[0].stop == pytest.approx(4.0)
        assert not result.bouts[0].is_point

    def test_point_event_from_ethogram(self, tmp_path):
        project = _boris_project(
            ethogram={"0": {"name": "scratch", "type": "Point event"}},
            observations={
                "obs1": {
                    "events": [[2.0, "ind1", "scratch", "", ""]],
                    "file": {},
                }
            },
        )
        p = self._write_project(tmp_path, project)
        result = _parse_boris_project(tmp_path / "test.boris")
        assert len(result.bouts) == 1
        assert result.bouts[0].is_point

    def test_media_filename_from_file_key(self, tmp_path):
        project = _boris_project(
            observations={
                "obs1": {
                    "events": [],
                    "file": {"1": ["/some/path/myvideo.mp4"]},
                }
            }
        )
        p = self._write_project(tmp_path, project)
        result = _parse_boris_project(tmp_path / "test.boris")
        assert result.media_filename == "myvideo.mp4"


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

class TestFormatDetection:
    def test_detects_tabular(self):
        df = pd.DataFrame({"Time": [], "Subject": [], "Behavior": [], "Status": []})
        assert _detect_csv_format(df) == "tabular"

    def test_detects_aggregated(self):
        df = pd.DataFrame({"Subject": [], "Behavior": [], "Start (s)": [], "Stop (s)": []})
        assert _detect_csv_format(df) == "aggregated"

    def test_aborts_on_unknown(self):
        df = pd.DataFrame({"foo": [], "bar": []})
        with pytest.raises(SystemExit):
            _detect_csv_format(df)


# ---------------------------------------------------------------------------
# Padding resolution
# ---------------------------------------------------------------------------

class TestPaddingResolution:
    def test_padding_sets_both(self):
        pre, post = _resolve_padding(2.0, None, None)
        assert pre == pytest.approx(2.0)
        assert post == pytest.approx(2.0)

    def test_padding_pre_overrides(self):
        pre, post = _resolve_padding(2.0, 1.0, None)
        assert pre == pytest.approx(1.0)
        assert post == pytest.approx(2.0)

    def test_padding_post_overrides(self):
        pre, post = _resolve_padding(2.0, None, 3.0)
        assert pre == pytest.approx(2.0)
        assert post == pytest.approx(3.0)

    def test_both_overrides(self):
        pre, post = _resolve_padding(2.0, 0.5, 4.0)
        assert pre == pytest.approx(0.5)
        assert post == pytest.approx(4.0)

    def test_no_padding_defaults_to_zero(self):
        pre, post = _resolve_padding(None, None, None)
        assert pre == pytest.approx(0.0)
        assert post == pytest.approx(0.0)
