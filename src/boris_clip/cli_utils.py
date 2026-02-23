"""Minimal logging/error utilities for core modules.

Core modules (parse, probe, validate, clip) import from here so they stay
decoupled from click. The CLI layer (cli.py) can replace these at runtime
if richer behaviour is needed — but the defaults work fine standalone.
"""

import sys


def warn(message: str) -> None:
    """Emit a warning to stderr."""
    print(f"Warning: {message}", file=sys.stderr)


def abort(message: str) -> None:
    """Print an error message and exit with code 1."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)
