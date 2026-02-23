"""Validation: cross-check BORIS annotations against video metadata."""

from .cli_utils import abort, warn

from .models import Bout, ParsedAnnotations, VideoInfo


# Tolerance for duration comparison (seconds)
_DURATION_TOLERANCE = 1.0
# Tolerance for FPS comparison
_FPS_TOLERANCE = 0.1


def validate(
    annotations: ParsedAnnotations,
    video: VideoInfo,
    force: bool = False,
) -> None:
    """Validate that BORIS annotations are consistent with the video file.

    Performs a series of checks with escalating severity. Hard errors call
    :func:`abort` unless ``force`` is ``True``, in which case they become
    warnings. Soft mismatches always produce warnings.

    Parameters
    ----------
    annotations:
        Parsed BORIS annotations.
    video:
        Video metadata from ffprobe.
    force:
        If ``True``, demote hard errors to warnings.
    """
    _check_media_filename(annotations, video, force)
    _check_fps(annotations, video)
    _check_duration(annotations, video)
    _check_bout_bounds(annotations, video, force)


def _hard(message: str, force: bool) -> None:
    if force:
        warn(f"{message} (continuing because --force was passed)")
    else:
        abort(f"{message} Pass --force to override.")


def _check_media_filename(
    annotations: ParsedAnnotations,
    video: VideoInfo,
    force: bool,
) -> None:
    if annotations.media_filename is None:
        warn("BORIS file does not contain a media filename reference — skipping filename check.")
        return

    if annotations.media_filename != video.filename:
        _hard(
            f"Media filename in BORIS file ({annotations.media_filename!r}) does not match "
            f"the provided video ({video.filename!r}).",
            force,
        )


def _check_fps(annotations: ParsedAnnotations, video: VideoInfo) -> None:
    if annotations.fps is None or video.fps == 0.0:
        return
    diff = abs(annotations.fps - video.fps)
    if diff > _FPS_TOLERANCE:
        warn(
            f"FPS in BORIS file ({annotations.fps:.4f}) differs from video FPS "
            f"({video.fps:.4f}). Re-encoded clips (default) will be frame-accurate; "
            "stream-copy (--fast) clips may have imprecise cut points."
        )


def _check_duration(annotations: ParsedAnnotations, video: VideoInfo) -> None:
    if annotations.duration is None:
        return
    diff = abs(annotations.duration - video.duration)
    if diff > _DURATION_TOLERANCE:
        warn(
            f"Duration in BORIS file ({annotations.duration:.3f}s) differs from "
            f"video duration ({video.duration:.3f}s) by {diff:.3f}s."
        )


def _check_bout_bounds(
    annotations: ParsedAnnotations,
    video: VideoInfo,
    force: bool,
) -> None:
    violations = [
        b for b in annotations.bouts if b.stop > video.duration + _DURATION_TOLERANCE
    ]
    if violations:
        details = "; ".join(
            f"{b.behaviour!r}/{b.subject!r} ends at {b.stop:.3f}s"
            for b in violations[:5]
        )
        if len(violations) > 5:
            details += f" ... and {len(violations) - 5} more"
        _hard(
            f"{len(violations)} bout(s) end after the video duration "
            f"({video.duration:.3f}s): {details}.",
            force,
        )
