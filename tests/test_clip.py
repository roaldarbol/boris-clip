# test_clip.py
#
# Tests:
# - build_output_path: correct filename pattern
# - build_output_path: zero-padding width scales with total count
# - build_output_path: special characters in names are sanitised
# - Bout.with_padding: padding is applied correctly
# - Bout.with_padding: start is clamped to 0
# - Bout.with_padding: stop is clamped to video duration
# - Bout.with_padding: point event padded correctly
# - extract_all_clips: creates output directory
# - extract_all_clips: per-group indexing is correct
# - extract_all_clips: zero-duration padded bouts are skipped

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from boris_clip.clip import build_output_path, extract_all_clips
from boris_clip.models import Bout, VideoInfo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def video():
    return VideoInfo(
        path="/data/recording.mp4",
        filename="recording.mp4",
        duration=120.0,
        fps=25.0,
    )


@pytest.fixture
def state_bout():
    return Bout(subject="ind1", behaviour="walking", start=10.0, stop=15.0)


@pytest.fixture
def point_bout():
    return Bout(subject="ind1", behaviour="scratch", start=20.0, stop=20.0, is_point=True)


# ---------------------------------------------------------------------------
# build_output_path
# ---------------------------------------------------------------------------

class TestBuildOutputPath:
    def test_filename_pattern(self, tmp_path, video, state_bout):
        p = build_output_path(state_bout, video, tmp_path, original_start=10.0, original_stop=15.0)
        assert p.name == "recording_walking_ind1_10.000-15.000.mp4"

    def test_no_focal_subject(self, tmp_path, video):
        bout = Bout(subject="No focal subject", behaviour="REM", start=1.5, stop=6.0)
        p = build_output_path(bout, video, tmp_path, original_start=1.5, original_stop=6.0)
        assert "no-focal-subject" in p.name
        assert "__" not in p.name

    def test_empty_subject(self, tmp_path, video):
        bout = Bout(subject="", behaviour="REM", start=1.5, stop=6.0)
        p = build_output_path(bout, video, tmp_path, original_start=1.5, original_stop=6.0)
        assert "no-focal-subject" in p.name
        assert "__" not in p.name

    def test_special_chars_sanitised(self, tmp_path, video):
        bout = Bout(subject="ind 1 (A)", behaviour="arm wave!", start=0.0, stop=5.0)
        p = build_output_path(bout, video, tmp_path, original_start=0.0, original_stop=5.0)
        import re
        assert re.fullmatch(r"[\w\-_.]+", p.name), f"Unexpected characters in {p.name!r}"


# ---------------------------------------------------------------------------
# Bout.with_padding
# ---------------------------------------------------------------------------

class TestBoutWithPadding:
    def test_padding_applied(self, state_bout):
        padded = state_bout.with_padding(pre=2.0, post=3.0)
        assert padded.start == pytest.approx(8.0)
        assert padded.stop == pytest.approx(18.0)

    def test_start_clamped_to_zero(self, state_bout):
        padded = state_bout.with_padding(pre=100.0)
        assert padded.start == pytest.approx(0.0)

    def test_stop_clamped_to_duration(self, state_bout):
        padded = state_bout.with_padding(post=200.0, video_duration=120.0)
        assert padded.stop == pytest.approx(120.0)

    def test_point_event_padded(self, point_bout):
        padded = point_bout.with_padding(pre=5.0, post=5.0)
        assert padded.start == pytest.approx(15.0)
        assert padded.stop == pytest.approx(25.0)
        assert padded.duration == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# extract_all_clips
# ---------------------------------------------------------------------------

class TestExtractAllClips:
    def _make_bouts(self):
        return [
            Bout("A", "run", 0.0, 5.0),
            Bout("A", "run", 10.0, 15.0),
            Bout("B", "run", 20.0, 25.0),
        ]

    @patch("boris_clip.clip.extract_clip")
    def test_creates_output_directory(self, mock_extract, tmp_path, video):
        out = tmp_path / "new_clips"
        extract_all_clips(self._make_bouts(), video, out)
        assert out.exists()

    @patch("boris_clip.clip.extract_clip")
    def test_interval_in_filename(self, mock_extract, tmp_path, video):
        bouts = self._make_bouts()
        extract_all_clips(bouts, video, tmp_path)
        names = [call.kwargs["output_path"].name for call in mock_extract.call_args_list]
        # Original bout times appear in filenames
        assert any("0.000-5.000" in n for n in names)
        assert any("10.000-15.000" in n for n in names)
        assert any("20.000-25.000" in n for n in names)

    @patch("boris_clip.clip.extract_clip")
    def test_zero_duration_bout_skipped(self, mock_extract, tmp_path, video):
        # A point event with no padding yields zero duration -> skipped
        bouts = [Bout("ind1", "scratch", 10.0, 10.0, is_point=True)]
        created = extract_all_clips(
            bouts, video, tmp_path,
            point_padding_pre=0.0,
            point_padding_post=0.0,
        )
        assert len(created) == 0
        mock_extract.assert_not_called()


# ---------------------------------------------------------------------------
# _apply_max_clips and max_duration
# ---------------------------------------------------------------------------

# Tests:
# - max_clips limits per (behaviour, subject) group, keeping earliest bouts
# - max_clips=None keeps all bouts
# - max_clips=1 keeps only the first bout per group
# - max_duration truncates long clips from the end after padding
# - max_duration=None does not truncate

class TestMaxClips:
    def _bouts(self):
        return [
            Bout("A", "REM", 0.0, 5.0),
            Bout("A", "REM", 10.0, 15.0),
            Bout("A", "REM", 20.0, 25.0),
            Bout("A", "walking", 5.0, 8.0),
            Bout("B", "REM", 1.0, 4.0),
        ]

    def test_limits_per_group(self):
        from boris_clip.clip import _apply_max_clips
        kept = _apply_max_clips(self._bouts(), max_clips=2)
        rem_a = [b for b in kept if b.behaviour == "REM" and b.subject == "A"]
        assert len(rem_a) == 2
        assert rem_a[0].start == pytest.approx(0.0)
        assert rem_a[1].start == pytest.approx(10.0)

    def test_none_keeps_all(self):
        from boris_clip.clip import _apply_max_clips
        assert len(_apply_max_clips(self._bouts(), None)) == 5

    def test_max_clips_one(self):
        from boris_clip.clip import _apply_max_clips
        kept = _apply_max_clips(self._bouts(), max_clips=1)
        rem_a = [b for b in kept if b.behaviour == "REM" and b.subject == "A"]
        assert len(rem_a) == 1
        assert rem_a[0].start == pytest.approx(0.0)

    @patch("boris_clip.clip.extract_clip")
    def test_max_duration_truncates(self, mock_extract, tmp_path, video):
        bouts = [Bout("A", "REM", 0.0, 30.0)]
        extract_all_clips(bouts, video, tmp_path, max_duration=10.0)
        call_bout = mock_extract.call_args.kwargs["bout"]
        assert call_bout.duration == pytest.approx(10.0)

    @patch("boris_clip.clip.extract_clip")
    def test_max_duration_none_no_truncation(self, mock_extract, tmp_path, video):
        bouts = [Bout("A", "REM", 0.0, 30.0)]
        extract_all_clips(bouts, video, tmp_path, max_duration=None)
        call_bout = mock_extract.call_args.kwargs["bout"]
        assert call_bout.duration == pytest.approx(30.0)