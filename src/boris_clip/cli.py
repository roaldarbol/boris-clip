"""Command-line interface for boris-clip."""

import sys
from pathlib import Path

import click

from .clip import extract_all_clips
from .models import ParsedAnnotations, VideoInfo
from .parse import parse_boris_file
from .probe import probe_video
from .validate import validate

_DEFAULT_POINT_PADDING = 5.0

# ---------------------------------------------------------------------------
# Pretty printing helpers
# ---------------------------------------------------------------------------

def _header(text: str) -> None:
    click.echo("")
    click.echo(click.style(text, bold=True, fg="cyan"))


def _item(label: str, value: str) -> None:
    click.echo(f"  {click.style(label, dim=True)}: {value}")


def _warn_pretty(text: str) -> None:
    click.echo(click.style(f"  Warning: {text}", fg="yellow"), err=True)


def _progress(current: int, total: int, path: Path) -> None:
    width = len(str(total))
    idx = click.style(f"[{current:{width}d}/{total}]", dim=True)
    click.echo(f"  {idx} {path.name}")


# ---------------------------------------------------------------------------
# Padding resolution
# ---------------------------------------------------------------------------

def _resolve_padding(
    padding: float | None,
    padding_pre: float | None,
    padding_post: float | None,
) -> tuple[float, float]:
    """Resolve CSS-like padding args into (pre, post).

    ``--padding`` sets both sides; ``--padding-pre`` / ``--padding-post``
    override their respective side.
    """
    base = padding if padding is not None else 0.0
    return (
        padding_pre if padding_pre is not None else base,
        padding_post if padding_post is not None else base,
    )


def _resolve_point_padding(
    padding_pre: float,
    padding_post: float,
    point_padding: float | None,
    point_padding_pre: float | None,
    point_padding_post: float | None,
    any_padding_specified: bool,
) -> tuple[float, float]:
    """Resolve padding for point events.

    Falls back to general padding if set, otherwise uses the 5s default.
    """
    if any(x is not None for x in [point_padding, point_padding_pre, point_padding_post]):
        base = point_padding if point_padding is not None else _DEFAULT_POINT_PADDING
        return (
            point_padding_pre if point_padding_pre is not None else base,
            point_padding_post if point_padding_post is not None else base,
        )
    if any_padding_specified:
        return padding_pre, padding_post
    return _DEFAULT_POINT_PADDING, _DEFAULT_POINT_PADDING


# ---------------------------------------------------------------------------
# Observation / video matching
# ---------------------------------------------------------------------------

def _match_observations(
    observations: list[ParsedAnnotations],
    video_paths: list[str],
) -> list[tuple[ParsedAnnotations, str]]:
    """Match observations to video files by filename.

    Returns (annotation, resolved_video_path) pairs for every observation
    that can be matched. Unmatched observations are skipped with a warning.

    If video_paths is provided, observations are matched by comparing their
    media_filename against the basenames of the supplied paths. If video_paths
    is empty, the embedded media_path from each observation is used directly
    (only available in .boris project files).
    """
    matched: list[tuple[ParsedAnnotations, str]] = []

    if video_paths:
        provided: dict[str, str] = {Path(vp).name: vp for vp in video_paths}
        for obs in observations:
            key = obs.media_filename or (Path(obs.media_path).name if obs.media_path else None)
            if key and key in provided:
                matched.append((obs, provided[key]))
            else:
                label = obs.obs_id or obs.media_filename or "unknown"
                _warn_pretty(
                    f"Observation {label!r}: no matching video found among provided paths — skipping."
                )
    else:
        for obs in observations:
            if obs.media_path:
                matched.append((obs, obs.media_path))
            else:
                label = obs.obs_id or "unknown"
                _warn_pretty(
                    f"Observation {label!r}: no video path in BORIS file and none provided — skipping."
                )

    return matched


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.argument("boris_file", metavar="BORIS_FILE", type=click.Path(exists=True, dir_okay=False))
@click.argument("videos", metavar="[VIDEO ...]", nargs=-1, type=click.Path(dir_okay=False))
@click.option(
    "--output-dir", "-o",
    default="clips", show_default=True,
    type=click.Path(file_okay=False),
    help="Directory to write output clips into.",
)
@click.option(
    "--padding", type=float, default=None, metavar="SECONDS",
    help="Add this many seconds before and after each bout.",
)
@click.option(
    "--padding-pre", type=float, default=None, metavar="SECONDS",
    help="Seconds before each bout (overrides --padding).",
)
@click.option(
    "--padding-post", type=float, default=None, metavar="SECONDS",
    help="Seconds after each bout (overrides --padding).",
)
@click.option(
    "--point-padding", type=float, default=None, metavar="SECONDS",
    help=(
        f"Padding for point events (both sides). "
        f"Defaults to {_DEFAULT_POINT_PADDING}s if no general padding is set."
    ),
)
@click.option(
    "--point-padding-pre", type=float, default=None, metavar="SECONDS",
    help="Pre-padding for point events (overrides --point-padding).",
)
@click.option(
    "--point-padding-post", type=float, default=None, metavar="SECONDS",
    help="Post-padding for point events (overrides --point-padding).",
)
@click.option(
    "--fast", is_flag=True, default=False,
    help=(
        "Use stream-copy instead of re-encoding. Much faster, but cuts snap to "
        "the nearest keyframe so clips may start/end slightly off."
    ),
)
@click.option(
    "--force", is_flag=True, default=False,
    help="Treat media-file mismatch and out-of-bounds errors as warnings rather than errors.",
)
@click.version_option()
def main(
    boris_file: str,
    videos: tuple[str, ...],
    output_dir: str,
    padding: float | None,
    padding_pre: float | None,
    padding_post: float | None,
    point_padding: float | None,
    point_padding_pre: float | None,
    point_padding_post: float | None,
    fast: bool,
    force: bool,
) -> None:
    """Extract video clips for each behavioural bout in a BORIS annotation file.

    BORIS_FILE is a BORIS annotation file (.boris project, tabular events CSV,
    or aggregated events CSV).

    VIDEO paths are optional. If omitted, paths embedded in the .boris project
    file are used. Multiple videos can be provided and will be matched to
    observations by filename.

    Output clips are named:

        {video_stem}_{behaviour}_{subject}_{start}-{stop}.mp4

    \b
    Examples
    --------
    Video path from .boris file:

        boris-clip annotations.boris

    Explicit video:

        boris-clip annotations.boris recording.mp4

    Multiple videos:

        boris-clip annotations.boris rec1.mp4 rec2.mp4

    With padding:

        boris-clip annotations.boris --padding 2.0 -o clips/
    """
    any_padding_specified = any(x is not None for x in [padding, padding_pre, padding_post])
    pre, post = _resolve_padding(padding, padding_pre, padding_post)
    pt_pre, pt_post = _resolve_point_padding(
        pre, post, point_padding, point_padding_pre, point_padding_post, any_padding_specified
    )

    # -- Parse BORIS file -------------------------------------------------------
    _header("Parsing BORIS file")
    _item("Path", boris_file)
    observations = parse_boris_file(boris_file)
    _item("Observations", str(len(observations)))
    _item("Format", observations[0].source_format if observations else "unknown")

    # -- Match observations to videos ------------------------------------------
    _header("Matching observations to videos")
    matched = _match_observations(observations, list(videos))

    if not matched:
        click.echo(click.style("\n  No observations could be matched to a video. Nothing to do.", fg="red"))
        sys.exit(1)

    # -- Process each matched pair ---------------------------------------------
    total_created: list[Path] = []

    for obs, video_path in matched:
        label = obs.obs_id or obs.media_filename or video_path
        _header(f"Observation: {label}")

        if not obs.bouts:
            _warn_pretty("No bouts found — skipping.")
            continue

        if not Path(video_path).exists():
            _warn_pretty(f"Video not found: {video_path!r} — skipping.")
            continue

        _item("Video", video_path)
        video_info: VideoInfo = probe_video(video_path)
        _item("Duration", f"{video_info.duration:.3f}s")
        _item("FPS", f"{video_info.fps:.4f}")

        validate(obs, video_info, force=force)

        n_state = sum(1 for b in obs.bouts if not b.is_point)
        n_point = sum(1 for b in obs.bouts if b.is_point)
        _item("Bouts", f"{len(obs.bouts)}  ({n_state} state, {n_point} point)")
        if n_state > 0:
            _item("State padding", f"pre {pre:.1f}s  /  post {post:.1f}s")
        if n_point > 0:
            _item("Point padding", f"pre {pt_pre:.1f}s  /  post {pt_post:.1f}s")
        _item("Mode", "stream-copy (--fast)" if fast else "re-encode")
        _item("Output", f"{output_dir}/")

        click.echo("")
        created = extract_all_clips(
            bouts=obs.bouts,
            video=video_info,
            output_dir=Path(output_dir),
            padding_pre=pre,
            padding_post=post,
            point_padding_pre=pt_pre,
            point_padding_post=pt_post,
            fast=fast,
            progress_callback=_progress,
        )
        total_created.extend(created)

    # -- Summary ---------------------------------------------------------------
    click.echo("")
    click.echo(
        click.style("Done. ", bold=True)
        + click.style(f"{len(total_created)} clip(s)", fg="green", bold=True)
        + f" written to {click.style(output_dir + '/', bold=True)}"
    )
    click.echo("")


if __name__ == "__main__":
    main()