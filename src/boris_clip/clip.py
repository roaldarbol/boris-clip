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


def build_output_path(
    bout: Bout,
    video: VideoInfo,
    output_dir: Path,
    index: int,
    total: int,
) -> Path:
    """Construct the output file path for a clip.

    Pattern: ``{video_stem}_{behaviour}_{subject}_{index:0Nd}.mp4``

    Parameters
    ----------
    bout:
        The bout being extracted.
    video:
        Source video metadata.
    output_dir:
        Directory to write clips into.
    index:
        1-based index of this clip within its (behaviour, subject) group.
    total:
        Total number of clips in this group (used to determine zero-padding width).
    """
    pad_width = max(2, len(str(total)))
    video_stem = Path(video.filename).stem
    behaviour = _sanitise_name(bout.behaviour)
    subject = _sanitise_name(bout.subject)
    filename = f"{video_stem}_{behaviour}_{subject}_{index:0{pad_width}d}.mp4"
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


def extract_all_clips(
    bouts: list[Bout],
    video: VideoInfo,
    output_dir: Path,
    padding_pre: float = 0.0,
    padding_post: float = 0.0,
    point_padding_pre: float = 5.0,
    point_padding_post: float = 5.0,
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

    # Count per (behaviour, subject) group to determine zero-padding width
    group_counts: dict[tuple[str, str], int] = {}
    for bout in bouts:
        key = (bout.behaviour, bout.subject)
        group_counts[key] = group_counts.get(key, 0) + 1

    group_indices: dict[tuple[str, str], int] = {}
    created: list[Path] = []

    for i, bout in enumerate(bouts):
        key = (bout.behaviour, bout.subject)
        group_indices[key] = group_indices.get(key, 0) + 1

        pre = point_padding_pre if bout.is_point else padding_pre
        post = point_padding_post if bout.is_point else padding_post
        padded = bout.with_padding(pre=pre, post=post, video_duration=video.duration)

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
            index=group_indices[key],
            total=group_counts[key],
        )

        if progress_callback is not None:
            progress_callback(i + 1, len(bouts), out_path)

        extract_clip(bout=padded, video=video, output_path=out_path, fast=fast)
        created.append(out_path)

    return created
