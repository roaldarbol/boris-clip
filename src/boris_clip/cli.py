"""Command-line interface for boris-clip."""

import sys
from pathlib import Path

import click

from .clip import extract_all_clips
from .models import ParsedAnnotations, VideoInfo
from .parse import parse_boris_file
from .probe import probe_video
from .validate import validate

# Default point-event padding (seconds each side)
_DEFAULT_POINT_PADDING = 5.0


def _resolve_padding(
    padding: float | None,
    padding_pre: float | None,
    padding_post: float | None,
) -> tuple[float, float]:
    """Resolve the CSS-like padding arguments into (pre, post) seconds.

    Precedence: --padding sets both; --padding-pre / --padding-post override
    their respective sides.
    """
    base_pre = padding if padding is not None else 0.0
    base_post = padding if padding is not None else 0.0
    resolved_pre = padding_pre if padding_pre is not None else base_pre
    resolved_post = padding_post if padding_post is not None else base_post
    return resolved_pre, resolved_post


def _resolve_point_padding(
    padding_pre: float,
    padding_post: float,
    point_padding: float | None,
    point_padding_pre: float | None,
    point_padding_post: float | None,
    any_padding_specified: bool,
) -> tuple[float, float]:
    """Resolve padding for point events.

    If the user specified any general padding, that is used for point events
    too (unless explicitly overridden with --point-padding-*). If no padding
    was specified at all, the default 5s each side is used.
    """
    if point_padding is not None or point_padding_pre is not None or point_padding_post is not None:
        base = point_padding if point_padding is not None else _DEFAULT_POINT_PADDING
        pre = point_padding_pre if point_padding_pre is not None else base
        post = point_padding_post if point_padding_post is not None else base
        return pre, post

    if any_padding_specified:
        return padding_pre, padding_post

    return _DEFAULT_POINT_PADDING, _DEFAULT_POINT_PADDING


@click.command()
@click.argument("video", type=click.Path(exists=True, dir_okay=False))
@click.argument("boris_file", metavar="BORIS_FILE", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--output-dir", "-o",
    default="clips",
    show_default=True,
    type=click.Path(file_okay=False),
    help="Directory to write output clips into.",
)
@click.option(
    "--padding",
    type=float,
    default=None,
    metavar="SECONDS",
    help="Add this many seconds before and after each bout.",
)
@click.option(
    "--padding-pre",
    type=float,
    default=None,
    metavar="SECONDS",
    help="Seconds to add before each bout (overrides --padding for the pre side).",
)
@click.option(
    "--padding-post",
    type=float,
    default=None,
    metavar="SECONDS",
    help="Seconds to add after each bout (overrides --padding for the post side).",
)
@click.option(
    "--point-padding",
    type=float,
    default=None,
    metavar="SECONDS",
    help=(
        f"Padding for point events (both sides). "
        f"Defaults to {_DEFAULT_POINT_PADDING}s if no general padding is set."
    ),
)
@click.option(
    "--point-padding-pre",
    type=float,
    default=None,
    metavar="SECONDS",
    help="Pre-padding for point events (overrides --point-padding for the pre side).",
)
@click.option(
    "--point-padding-post",
    type=float,
    default=None,
    metavar="SECONDS",
    help="Post-padding for point events (overrides --point-padding for the post side).",
)
@click.option(
    "--fast",
    is_flag=True,
    default=False,
    help=(
        "Use stream-copy instead of re-encoding. Much faster, but cuts snap to "
        "the nearest keyframe so clips may start/end slightly off."
    ),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Treat media-file mismatch and out-of-bounds errors as warnings rather than errors.",
)
@click.version_option()
def main(
    video: str,
    boris_file: str,
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

    VIDEO is the path to the source video file.
    BORIS_FILE is a BORIS annotation file (.boris project, tabular events CSV,
    or aggregated events CSV).

    Output clips are written to OUTPUT_DIR and named:

        {video_stem}_{behaviour}_{subject}_{index}.mp4

    \b
    Examples
    --------
    Basic extraction:

        boris-clip recording.mp4 annotations.boris

    With padding and a specific output directory:

        boris-clip recording.mp4 annotations.boris -o clips/ --padding 2.0

    Asymmetric padding (1s before, 3s after):

        boris-clip recording.mp4 annotations.boris --padding-pre 1.0 --padding-post 3.0

    Fast stream-copy (approximate cuts, no re-encoding):

        boris-clip recording.mp4 annotations.boris --fast
    """
    any_padding_specified = any(
        x is not None for x in [padding, padding_pre, padding_post]
    )
    pre, post = _resolve_padding(padding, padding_pre, padding_post)
    pt_pre, pt_post = _resolve_point_padding(
        pre, post, point_padding, point_padding_pre, point_padding_post, any_padding_specified
    )

    click.echo(f"Probing video: {video}")
    video_info: VideoInfo = probe_video(video)
    click.echo(
        f"  Duration: {video_info.duration:.3f}s  |  FPS: {video_info.fps:.4f}  |  {video_info.filename}"
    )

    click.echo(f"Parsing BORIS file: {boris_file}")
    annotations: ParsedAnnotations = parse_boris_file(boris_file)
    click.echo(
        f"  Format: {annotations.source_format}  |  Bouts: {len(annotations.bouts)}"
    )

    click.echo("Validating annotations against video...")
    validate(annotations, video_info, force=force)
    click.echo("  OK")

    n_state = sum(1 for b in annotations.bouts if not b.is_point)
    n_point = sum(1 for b in annotations.bouts if b.is_point)
    click.echo(
        f"\nExtracting {len(annotations.bouts)} clips "
        f"({n_state} state events, {n_point} point events)"
    )
    if n_state > 0:
        click.echo(f"  State padding  — pre: {pre:.1f}s  post: {post:.1f}s")
    if n_point > 0:
        click.echo(f"  Point padding  — pre: {pt_pre:.1f}s  post: {pt_post:.1f}s")
    click.echo(f"  Mode: {'stream-copy (--fast)' if fast else 're-encode (default)'}")
    click.echo(f"  Output: {output_dir}/\n")

    def _progress(current: int, total: int, path: Path) -> None:
        width = len(str(total))
        click.echo(f"  [{current:{width}d}/{total}] {path.name}")

    created = extract_all_clips(
        bouts=annotations.bouts,
        video=video_info,
        output_dir=Path(output_dir),
        padding_pre=pre,
        padding_post=post,
        point_padding_pre=pt_pre,
        point_padding_post=pt_post,
        fast=fast,
        progress_callback=_progress,
    )

    click.echo(f"\nDone. {len(created)} clip(s) written to {output_dir}/")
