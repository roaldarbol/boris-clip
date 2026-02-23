"""BORIS annotation file parser.

Supports:
- .boris project files (JSON)
- Tabular events CSV export
- Aggregated events CSV export

All formats are normalised into a list of Bout objects.
"""

import json
from pathlib import Path

import pandas as pd

from .cli_utils import abort, warn

from .models import Bout, ParsedAnnotations


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _is_boris_project(path: Path) -> bool:
    return path.suffix.lower() == ".boris"


def _detect_csv_format(df: pd.DataFrame) -> str:
    """Detect whether a CSV is tabular events or aggregated events."""
    cols = {c.strip().lower() for c in df.columns}
    if "start (s)" in cols and "stop (s)" in cols:
        return "aggregated"
    if "time" in cols and "status" in cols:
        return "tabular"
    # Older BORIS used 'behavior type' in tabular exports
    if "time" in cols and "behavior type" in cols:
        return "tabular_legacy"
    abort(
        "Could not detect BORIS CSV format. "
        "Expected either a tabular events export (with 'Time' and 'Status' columns) "
        "or an aggregated events export (with 'Start (s)' and 'Stop (s)' columns)."
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _sanitise_str(value) -> str:
    """Strip and normalise a string value from a BORIS file."""
    return str(value).strip() if pd.notna(value) else ""


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first column name (case-insensitive) matching any candidate."""
    lower_map = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def _require_col(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    col = _find_col(df, candidates)
    if col is None:
        abort(f"Could not find required column {label!r} in BORIS file. "
              f"Tried: {candidates}")
    return col


# ---------------------------------------------------------------------------
# Tabular events CSV parser
# ---------------------------------------------------------------------------

def _parse_tabular_csv(df: pd.DataFrame, path: Path) -> ParsedAnnotations:
    """Parse a BORIS tabular events export."""
    col_time = _require_col(df, ["Time"], "Time")
    col_subject = _require_col(df, ["Subject"], "Subject")
    col_behaviour = _require_col(df, ["Behavior", "Behaviour"], "Behavior")
    col_status = _require_col(df, ["Status", "Behavior type", "Behaviour type"], "Status")
    col_media = _find_col(df, ["Media file path", "Media file name", "Media file"])

    media_filename: str | None = None
    fps: float | None = None
    duration: float | None = None

    if col_media is not None:
        filenames = df[col_media].dropna().unique()
        if len(filenames) == 1:
            media_filename = Path(_sanitise_str(filenames[0])).name
        elif len(filenames) > 1:
            warn(
                f"Multiple media files found in BORIS export: {list(filenames)}. "
                "Validation will check against the first non-empty value."
            )
            media_filename = Path(_sanitise_str(filenames[0])).name

    col_fps = _find_col(df, ["FPS", "Fps"])
    if col_fps is not None:
        fps_vals = pd.to_numeric(df[col_fps], errors="coerce").dropna().unique()
        if len(fps_vals) == 1:
            fps = float(fps_vals[0])

    col_duration = _find_col(df, ["Total length", "Duration"])
    if col_duration is not None:
        dur_vals = pd.to_numeric(df[col_duration], errors="coerce").dropna().unique()
        if len(dur_vals) == 1:
            duration = float(dur_vals[0])

    # Sort by time to ensure correct START/STOP pairing
    df = df.copy()
    df[col_time] = pd.to_numeric(df[col_time], errors="coerce")
    df = df.dropna(subset=[col_time]).sort_values(col_time)

    bouts: list[Bout] = []
    # Track open state events: (subject, behaviour) -> start_time
    open_states: dict[tuple[str, str], float] = {}

    for _, row in df.iterrows():
        t = float(row[col_time])
        subject = _sanitise_str(row[col_subject])
        behaviour = _sanitise_str(row[col_behaviour])
        status = _sanitise_str(row[col_status]).upper()

        if status in ("START",):
            key = (subject, behaviour)
            if key in open_states:
                warn(
                    f"Found START for ({subject!r}, {behaviour!r}) at t={t:.3f}s "
                    f"before previous START at t={open_states[key]:.3f}s was closed. "
                    "Closing the previous bout implicitly."
                )
            open_states[key] = t

        elif status in ("STOP",):
            key = (subject, behaviour)
            if key not in open_states:
                warn(
                    f"Found STOP for ({subject!r}, {behaviour!r}) at t={t:.3f}s "
                    "with no matching START. Skipping."
                )
                continue
            bouts.append(
                Bout(
                    subject=subject,
                    behaviour=behaviour,
                    start=open_states.pop(key),
                    stop=t,
                    is_point=False,
                )
            )

        elif status in ("POINT", "PUNCTUAL"):
            bouts.append(
                Bout(
                    subject=subject,
                    behaviour=behaviour,
                    start=t,
                    stop=t,
                    is_point=True,
                )
            )
        else:
            warn(f"Unknown event status {status!r} at t={t:.3f}s — skipping row.")

    for (subject, behaviour), start in open_states.items():
        warn(
            f"State event ({subject!r}, {behaviour!r}) opened at t={start:.3f}s "
            "was never closed. Skipping."
        )

    return ParsedAnnotations(
        bouts=bouts,
        media_filename=media_filename,
        fps=fps,
        duration=duration,
        source_format="tabular_csv",
    )


# ---------------------------------------------------------------------------
# Aggregated events CSV parser
# ---------------------------------------------------------------------------

def _parse_aggregated_csv(df: pd.DataFrame, path: Path) -> ParsedAnnotations:
    """Parse a BORIS aggregated events export."""
    col_subject = _require_col(df, ["Subject"], "Subject")
    col_behaviour = _require_col(df, ["Behavior", "Behaviour"], "Behavior")
    col_start = _require_col(df, ["Start (s)", "Start(s)"], "Start (s)")
    col_stop = _require_col(df, ["Stop (s)", "Stop(s)"], "Stop (s)")
    col_media = _find_col(df, ["Media file path", "Media file name", "Media file"])

    media_filename: str | None = None
    fps: float | None = None
    duration: float | None = None

    if col_media is not None:
        filenames = df[col_media].dropna().unique()
        if len(filenames) >= 1:
            media_filename = Path(_sanitise_str(filenames[0])).name

    col_fps = _find_col(df, ["FPS", "Fps"])
    if col_fps is not None:
        fps_vals = pd.to_numeric(df[col_fps], errors="coerce").dropna().unique()
        if len(fps_vals) == 1:
            fps = float(fps_vals[0])

    col_total = _find_col(df, ["Total length", "Duration"])
    if col_total is not None:
        dur_vals = pd.to_numeric(df[col_total], errors="coerce").dropna().unique()
        if len(dur_vals) == 1:
            duration = float(dur_vals[0])

    bouts: list[Bout] = []
    for _, row in df.iterrows():
        subject = _sanitise_str(row[col_subject])
        behaviour = _sanitise_str(row[col_behaviour])
        start = pd.to_numeric(row[col_start], errors="coerce")
        stop = pd.to_numeric(row[col_stop], errors="coerce")

        if pd.isna(start) or pd.isna(stop):
            warn(f"Skipping row with missing start/stop for ({subject!r}, {behaviour!r}).")
            continue

        start, stop = float(start), float(stop)
        is_point = start == stop

        bouts.append(
            Bout(
                subject=subject,
                behaviour=behaviour,
                start=start,
                stop=stop,
                is_point=is_point,
            )
        )

    return ParsedAnnotations(
        bouts=bouts,
        media_filename=media_filename,
        fps=fps,
        duration=duration,
        source_format="aggregated_csv",
    )


# ---------------------------------------------------------------------------
# .boris project file parser
# ---------------------------------------------------------------------------

def _parse_boris_project(path: Path) -> ParsedAnnotations:
    """Parse a BORIS .boris project file (JSON)."""
    with open(path, encoding="utf-8") as fh:
        project = json.load(fh)

    ethogram: dict[str, str] = {}  # behaviour_name -> "State event" | "Point event"
    for entry in project.get("ethogram", {}).values():
        name = entry.get("name", "").strip()
        btype = entry.get("type", "").strip()
        if name:
            ethogram[name] = btype

    observations = project.get("observations", {})
    if not observations:
        abort("No observations found in .boris project file.")

    if len(observations) > 1:
        warn(
            f"Project file contains {len(observations)} observations. "
            "All will be parsed and combined. Use --observation to filter (not yet implemented)."
        )

    bouts: list[Bout] = []
    media_filename: str | None = None
    fps: float | None = None
    duration: float | None = None

    for obs_id, obs in observations.items():
        # Extract media info
        media_info = obs.get("media_info", {})
        media_file = obs.get("file", obs.get("media_file_name", {}))

        if isinstance(media_file, dict):
            # Keyed by player number {"1": ["/path/to/file.mp4"]}
            for player_files in media_file.values():
                if isinstance(player_files, list) and player_files:
                    media_filename = Path(player_files[0]).name
                    break
                elif isinstance(player_files, str):
                    media_filename = Path(player_files).name
                    break
        elif isinstance(media_file, str) and media_file:
            media_filename = Path(media_file).name

        # FPS and duration from media_info if present
        if isinstance(media_info, dict):
            for player_info in media_info.values():
                if isinstance(player_info, dict):
                    for file_info in player_info.values():
                        if isinstance(file_info, dict):
                            if fps is None and "fps" in file_info:
                                try:
                                    fps = float(file_info["fps"])
                                except (ValueError, TypeError):
                                    pass
                            if duration is None and "duration" in file_info:
                                try:
                                    duration = float(file_info["duration"])
                                except (ValueError, TypeError):
                                    pass

        # Parse events
        # Events are: [time, subject, behavior, modifier, comment]
        # State events are paired: 1st occurrence = START, 2nd = STOP, per (subject, behaviour)
        events = obs.get("events", [])
        open_states: dict[tuple[str, str], float] = {}

        for event in sorted(events, key=lambda e: e[0]):
            if len(event) < 3:
                continue
            t = float(event[0])
            subject = str(event[1]).strip()
            behaviour = str(event[2]).strip()

            event_type = ethogram.get(behaviour, "State event")

            if "point" in event_type.lower():
                bouts.append(
                    Bout(
                        subject=subject,
                        behaviour=behaviour,
                        start=t,
                        stop=t,
                        is_point=True,
                    )
                )
            else:
                # State event: toggle open/close
                key = (subject, behaviour)
                if key in open_states:
                    bouts.append(
                        Bout(
                            subject=subject,
                            behaviour=behaviour,
                            start=open_states.pop(key),
                            stop=t,
                            is_point=False,
                        )
                    )
                else:
                    open_states[key] = t

        for (subject, behaviour), start in open_states.items():
            warn(
                f"[{obs_id}] State event ({subject!r}, {behaviour!r}) opened at "
                f"t={start:.3f}s was never closed. Skipping."
            )

    return ParsedAnnotations(
        bouts=bouts,
        media_filename=media_filename,
        fps=fps,
        duration=duration,
        source_format="boris_project",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _read_csv_skip_header(path: Path) -> pd.DataFrame:
    """Read a BORIS CSV, skipping any non-tabular header lines."""
    # BORIS sometimes prepends metadata lines before the actual header.
    # We find the first line that looks like a real header by searching for
    # known column names.
    known_headers = {"time", "subject", "behavior", "behaviour", "start (s)"}
    with open(path, encoding="utf-8-sig") as fh:
        lines = fh.readlines()

    skip = 0
    for i, line in enumerate(lines):
        lower = line.lower()
        if any(h in lower for h in known_headers):
            skip = i
            break

    return pd.read_csv(path, skiprows=skip, encoding="utf-8-sig")


def parse_boris_file(path: str) -> ParsedAnnotations:
    """Parse a BORIS annotation file in any supported format.

    Supported formats are detected automatically:

    - ``.boris`` — BORIS project file (JSON)
    - CSV tabular events export
    - CSV aggregated events export

    Parameters
    ----------
    path:
        Path to the BORIS file.

    Returns
    -------
    ParsedAnnotations
        Parsed bouts and any available media metadata.
    """
    p = Path(path)
    if not p.exists():
        abort(f"BORIS file not found: {path!r}")

    if _is_boris_project(p):
        return _parse_boris_project(p)

    try:
        df = _read_csv_skip_header(p)
    except Exception as e:
        abort(f"Could not read {path!r} as CSV: {e}")

    fmt = _detect_csv_format(df)
    if fmt in ("tabular", "tabular_legacy"):
        return _parse_tabular_csv(df, p)
    else:
        return _parse_aggregated_csv(df, p)
