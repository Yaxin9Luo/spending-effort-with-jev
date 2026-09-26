"""Compute when a cron schedule fires next.

Used by the job runner to show "next run" times and to decide what to wake up for.
"""
from datetime import datetime


def next_run(expr: str, after: datetime) -> datetime:
    """Return the first time strictly after `after` at which cron expression `expr` fires."""
    raise NotImplementedError
