"""Local wall-clock access."""

from datetime import datetime


def local_now() -> datetime:
    """Return the computer's current local wall-clock time."""
    return datetime.now()
