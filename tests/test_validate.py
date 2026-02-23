# test_validate.py
#
# Tests:
# - No error when media filenames match
# - Hard error when filenames differ (no --force)
# - Warning (not error) when filenames differ with --force
# - Warning when FPS differs beyond tolerance
# - No warning when FPS matches
# - Warning when BORIS duration differs from video duration
# - Hard error when bout end exceeds video duration
# - No error when bout is within bounds
# - No filename check when BORIS file has no media info

import pytest

from boris_clip.models import Bout, ParsedAnnotations, VideoInfo
from boris_clip.validate import validate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _video(**kwargs):
    defaults = dict(path="/data/v.mp4", filename="v.mp4", duration=60.0, fps=25.0)
    return VideoInfo(**{**defaults, **kwargs})


def _annotations(**kwargs):
    defaults = dict(bouts=[], media_filename="v.mp4", fps=25.0, duration=60.0)
    return ParsedAnnotations(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# Filename validation
# ---------------------------------------------------------------------------

class TestFilenameValidation:
    def test_matching_filenames_ok(self):
        validate(_annotations(), _video())  # should not raise

    def test_mismatch_raises(self):
        ann = _annotations(media_filename="other.mp4")
        with pytest.raises(SystemExit):
            validate(ann, _video())

    def test_mismatch_with_force_warns(self, capsys):
        ann = _annotations(media_filename="other.mp4")
        validate(ann, _video(), force=True)  # should not raise
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    def test_no_media_filename_skips_check(self, capsys):
        ann = _annotations(media_filename=None)
        validate(ann, _video())  # should not raise
        captured = capsys.readouterr()
        assert "skipping filename check" in captured.err


# ---------------------------------------------------------------------------
# FPS validation
# ---------------------------------------------------------------------------

class TestFPSValidation:
    def test_fps_mismatch_warns(self, capsys):
        ann = _annotations(fps=30.0)
        validate(ann, _video(fps=25.0))
        captured = capsys.readouterr()
        assert "FPS" in captured.err

    def test_fps_match_no_warning(self, capsys):
        ann = _annotations(fps=25.0)
        validate(ann, _video(fps=25.0))
        captured = capsys.readouterr()
        assert "FPS" not in captured.err


# ---------------------------------------------------------------------------
# Duration validation
# ---------------------------------------------------------------------------

class TestDurationValidation:
    def test_duration_mismatch_warns(self, capsys):
        ann = _annotations(duration=70.0)
        validate(ann, _video(duration=60.0))
        captured = capsys.readouterr()
        assert "Duration" in captured.err or "duration" in captured.err

    def test_duration_within_tolerance_ok(self, capsys):
        ann = _annotations(duration=60.5)
        validate(ann, _video(duration=60.0))
        captured = capsys.readouterr()
        # 0.5s difference is within 1.0s tolerance
        assert "duration" not in captured.err.lower()


# ---------------------------------------------------------------------------
# Bout bounds
# ---------------------------------------------------------------------------

class TestBoutBounds:
    def test_out_of_bounds_raises(self):
        bout = Bout("ind1", "run", 55.0, 65.0)
        ann = _annotations(bouts=[bout])
        with pytest.raises(SystemExit):
            validate(ann, _video(duration=60.0))

    def test_within_bounds_ok(self):
        bout = Bout("ind1", "run", 10.0, 20.0)
        ann = _annotations(bouts=[bout])
        validate(ann, _video(duration=60.0))  # should not raise

    def test_out_of_bounds_with_force(self, capsys):
        bout = Bout("ind1", "run", 55.0, 65.0)
        ann = _annotations(bouts=[bout])
        validate(ann, _video(duration=60.0), force=True)
        captured = capsys.readouterr()
        assert "Warning" in captured.err
