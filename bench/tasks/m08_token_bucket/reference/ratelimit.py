"""Rate limiting for the public API gateway."""
import time


class TokenBucket:
    def __init__(self, rate, capacity, clock=time.monotonic):
        if not rate > 0:
            raise ValueError("rate must be > 0")
        if not capacity > 0:
            raise ValueError("capacity must be > 0")
        self.rate = rate
        self.capacity = capacity
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()

    def _refill(self):
        now = self._clock()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last = now

    def _check(self, n):
        if not n > 0 or n > self.capacity:
            raise ValueError("n must be > 0 and <= capacity")

    @property
    def tokens(self):
        self._refill()
        return self._tokens

    def try_acquire(self, n=1):
        self._check(n)
        self._refill()
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False

    def wait_time(self, n=1):
        self._check(n)
        self._refill()
        if self._tokens >= n:
            return 0.0
        return (n - self._tokens) / self.rate


class KeyedRateLimiter:
    def __init__(self, rate, capacity, clock=time.monotonic):
        TokenBucket(rate, capacity, clock)  # validate eagerly
        self.rate = rate
        self.capacity = capacity
        self._clock = clock
        self._buckets = {}

    def allow(self, key, n=1):
        b = self._buckets.get(key)
        if b is None:
            b = self._buckets[key] = TokenBucket(self.rate, self.capacity, self._clock)
        return b.try_acquire(n)

    def __len__(self):
        return len(self._buckets)

    def cleanup(self):
        full = [k for k, b in self._buckets.items() if b.tokens >= b.capacity]
        for k in full:
            del self._buckets[k]
        return len(full)
