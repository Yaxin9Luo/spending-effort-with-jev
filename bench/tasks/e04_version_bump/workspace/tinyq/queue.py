from collections import deque


class JobQueue:
    """First-in, first-out queue of callables."""

    def __init__(self):
        self._jobs = deque()

    def submit(self, fn, *args, **kwargs):
        self._jobs.append((fn, args, kwargs))

    def __len__(self):
        return len(self._jobs)

    def run_next(self):
        fn, args, kwargs = self._jobs.popleft()
        return fn(*args, **kwargs)

    def drain(self):
        """Run every queued job in order and return their results."""
        results = []
        while self._jobs:
            results.append(self.run_next())
        return results
