"""Tiny job table for the runner: prints each job's next run time."""
import sys
from datetime import datetime

from cronnext import next_run

JOBS = {
    "rotate-logs": "0 0 * * *",
    "sync-billing": "*/15 * * * *",
    "month-end-report": "30 23 28-31 * *",
    "weekly-digest": "0 9 * * mon",
}


def main(argv=None):
    now = datetime.now()
    for name, expr in sorted(JOBS.items()):
        print(f"{name:20s} {expr:20s} {next_run(expr, now):%Y-%m-%d %H:%M}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
