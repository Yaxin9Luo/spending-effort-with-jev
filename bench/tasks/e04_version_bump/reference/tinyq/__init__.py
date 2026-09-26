"""tinyq - a tiny in-process job queue."""

__version__ = "1.5.0"
__version_info__ = (1, 5, 0)

from tinyq.queue import JobQueue  # noqa: E402

__all__ = ["JobQueue", "__version__", "__version_info__"]
