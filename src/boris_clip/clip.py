"""ffmpeg-based clip extraction."""

import re
import subprocess
from pathlib import Path

from .cli_utils import abort, warn

from .models import Bout, VideoInfo


def _sanitise_name(name: str) -> str:
    """Convert a BORIS name to a safe filename component."""
    name = name.strip()
    name = re.sub(r"[^\w\-]", "_", name)  # replace non-word chars with _
    name = re.sub(r"_+", "_", name)  # collapse multiple underscores
    return name.strip("_")


_NO_FOCAL_SUBJECT_LABELS = {"", "no focal subject", "no-focal-subject"}


def build_output_path(
    bout: Bout,
    video: VideoInfo,
    output_dir: Path,
    original_start: float,
    original_stop: float,
) -> Path:
    """Construct the output file path for a clip.

    Pattern: ``{video_stem}_{behaviour}_{subject}_{start}-{stop}.mp4``

    The time interval reflects the original (unpadded) bout times so that
    the filename is stable regardless of padding settings. When there is no
    focal subject the component is ``no-focal-subject``.

    Parameters
    ----------
    bout:
        The bout being extracted (may be padded).
    video:
        Source video metadata.
    output_dir:
        Directory to write clips into.
    original_start:
        Unpadded start time, used in the filename.
    original_stop:
        Unpadded stop time, used in the filename.
    """
    video_stem = Path(video.filename).stem
    behaviour = _sanitise_name(bout.behaviour)

    if bout.subject.strip().lower() in _NO_FOCAL_SUBJECT_LABELS:
        subject = "no-focal-subject"
    else:
        subject = _sanitise_name(bout.subject)

    interval = f"{original_start:.3f}-{original_stop:.3f}"
    parts = [video_stem, behaviour, subject, interval]
    filename = "_".join(p for p in parts if p) + ".mp4"
    return output_dir / filename


def extract_clip(
    bout: Bout,
    video: VideoInfo,
    output_path: Path,
    fast: bool = False,
) -> None:
    """Extract a single clip from a video using ffmpeg.

    Parameters
    ----------
    bout:
        Bout with (possibly padded) start and stop times.
    video:
        Source video metadata.
    output_path:
        Where to write the output clip.
    fast:
        If ``True``, use stream-copy (fast but keyframe-imprecise).
        If ``False`` (default), re-encode for frame-accurate cuts.
    """
    duration = bout.stop - bout.start

    if fast:
        # Stream copy: seek before input for speed; cuts snap to nearest keyframe
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", f"{bout.start:.6f}",
            "-i", video.path,
            "-t", f"{duration:.6f}",
            "-c", "copy",
            str(output_path),
        ]
    else:
        # Re-encode: seek after input for frame accuracy
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video.path,
            "-ss", f"{bout.start:.6f}",
            "-t", f"{duration:.6f}",
            str(output_path),
        ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        abort("ffmpeg not found. Please ensure ffmpeg is installed and on your PATH.")

    if result.returncode != 0:
        warn(
            f"ffmpeg returned non-zero exit code for {output_path.name!r}:\n"
            f"{result.stderr[-500:].strip()}"
        )


def _apply_max_clips(
    bouts: list[Bout],
    max_clips: int | None,
) -> list[Bout]:
    """Return at most max_clips bouts per (behaviour, subject) group.

    Bouts are assumed to be in chronological order; the first N per group
    are kept.
    """
    if max_clips is None:
        return bouts
    counts: dict[tuple[str, str], int] = {}
    kept: list[Bout] = []
    for bout in bouts:
        key = (bout.behaviour, bout.subject)
        n = counts.get(key, 0)
        if n < max_clips:
            kept.append(bout)
            counts[key] = n + 1
    return kept


def extract_all_clips(
    bouts: list[Bout],
    video: VideoInfo,
    output_dir: Path,
    padding_pre: float = 0.0,
    padding_post: float = 0.0,
    point_padding_pre: float = 5.0,
    point_padding_post: float = 5.0,
    max_duration: float | None = None,
    max_clips: int | None = None,
    fast: bool = False,
    progress_callback=None,
) -> list[Path]:
    """Extract clips for all bouts.

    Parameters
    ----------
    bouts:
        Bouts to extract.
    video:
        Source video metadata.
    output_dir:
        Directory to write clips into.
    padding_pre:
        Seconds to add before each state event bout.
    padding_post:
        Seconds to add after each state event bout.
    point_padding_pre:
        Seconds to add before each point event.
    point_padding_post:
        Seconds to add after each point event.
    max_duration:
        If set, clips longer than this many seconds are truncated from the end.
        Applied after padding.
    max_clips:
        If set, at most this many clips are extracted per (behaviour, subject)
        group. Earlier bouts take priority.
    fast:
        Use stream-copy instead of re-encoding.
    progress_callback:
        Optional callable ``(current, total, output_path)`` for progress reporting.

    Returns
    -------
    list[Path]
        Paths to all successfully created clips.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    bouts = _apply_max_clips(bouts, max_clips)
    created: list[Path] = []

    for i, bout in enumerate(bouts):
        pre = point_padding_pre if bout.is_point else padding_pre
        post = point_padding_post if bout.is_point else padding_post
        padded = bout.with_padding(pre=pre, post=post, video_duration=video.duration)

        # Truncate from the end if the padded clip exceeds max_duration
        if max_duration is not None and padded.duration > max_duration:
            padded = Bout(
                subject=padded.subject,
                behaviour=padded.behaviour,
                start=padded.start,
                stop=padded.start + max_duration,
                is_point=padded.is_point,
            )

        if padded.duration <= 0:
            warn(
                f"Bout ({bout.subject!r}, {bout.behaviour!r}) at t={bout.start:.3f}s "
                "has zero or negative duration after padding — skipping."
            )
            continue

        out_path = build_output_path(
            bout=padded,
            video=video,
            output_dir=output_dir,
            original_start=bout.start,
            original_stop=bout.stop,
        )

        if progress_callback is not None:
            progress_callback(i + 1, len(bouts), out_path)

        extract_clip(bout=padded, video=video, output_path=out_path, fast=fast)
        created.append(out_path)

    return created