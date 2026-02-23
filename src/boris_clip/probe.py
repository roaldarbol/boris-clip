"""ffprobe wrapper for extracting video metadata."""

import json
import os
import subprocess
from pathlib import Path

from .cli_utils import abort, warn

from .models import VideoInfo


def _run_ffprobe(video_path: str) -> dict:
    """Run ffprobe on a video file and return parsed JSON output."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        abort("ffprobe not found. Please ensure ffmpeg is installed and on your PATH.")
    except subprocess.CalledProcessError as e:
        abort(f"ffprobe failed for {video_path!r}: {e.stderr.strip()}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        abort(f"Could not parse ffprobe output for {video_path!r}.")


def probe_video(video_path: str) -> VideoInfo:
    """Extract metadata from a video file using ffprobe.

    Parameters
    ----------
    video_path:
        Path to the video file.

    Returns
    -------
    VideoInfo
        Parsed metadata including duration, fps, and filename.
    """
    data = _run_ffprobe(video_path)

    # Duration: prefer format-level, fall back to video stream
    duration: float | None = None
    if "format" in data and "duration" in data["format"]:
        try:
            duration = float(data["format"]["duration"])
        except (ValueError, TypeError):
            pass

    fps: float | None = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            if duration is None and "duration" in stream:
                try:
                    duration = float(stream["duration"])
                except (ValueError, TypeError):
                    pass
            if "r_frame_rate" in stream:
                try:
                    num, den = stream["r_frame_rate"].split("/")
                    fps = float(num) / float(den)
                except (ValueError, ZeroDivisionError):
                    pass
            break

    if duration is None:
        abort(f"Could not determine duration for {video_path!r}.")
    if fps is None:
        warn(f"Could not determine FPS for {video_path!r}. Frame-accurate seeking may be unreliable.")
        fps = 0.0

    return VideoInfo(
        path=os.path.abspath(video_path),
        filename=Path(video_path).name,
        duration=duration,
        fps=fps,
    )
