"""In-memory cache used by the web layer (see TTLCache)."""

import time
from collections import OrderedDict

_NEVER = None


def _check_ttl(ttl):
    if ttl is not None and not ttl > 0:
        raise ValueError("ttl must be > 0 or None")


class TTLCache:
    """LRU cache with per-entry expiry."""

    def __init__(self, maxsize, ttl=None, clock=time.monotonic):
        if isinstance(maxsize, bool) or not isinstance(maxsize, int) or maxsize <= 0:
            raise ValueError("maxsize must be a positive int")
        _check_ttl(ttl)
        self.maxsize = maxsize
        self.ttl = ttl
        self._clock = clock
        self._data = OrderedDict()  # key -> (value, expires_at or None)

    def _expired(self, expires_at, now):
        return expires_at is not None and now >= expires_at

    def _live(self, key, now):
        item = self._data.get(key)
        if item is None:
            return None
        if self._expired(item[1], now):
            del self._data[key]
            return None
        return item

    def _purge(self, now):
        for k in [k for k, (_, e) in self._data.items() if self._expired(e, now)]:
            del self._data[k]

    def set(self, key, value, ttl=None):
        _check_ttl(ttl)
        now = self._clock()
        eff = self.ttl if ttl is None else ttl
        expires_at = None if eff is None else now + eff
        if self._live(key, now) is not None:
            self._data[key] = (value, expires_at)
            self._data.move_to_end(key)
            return
        if len(self._data) >= self.maxsize:
            self._purge(now)
            while len(self._data) >= self.maxsize:
                self._data.popitem(last=False)
        self._data[key] = (value, expires_at)

    def get(self, key, default=None):
        item = self._live(key, self._clock())
        if item is None:
            return default
        self._data.move_to_end(key)
        return item[0]

    def delete(self, key):
        if self._live(key, self._clock()) is None:
            return False
        del self._data[key]
        return True

    def __contains__(self, key):
        return self._live(key, self._clock()) is not None

    def __len__(self):
        self._purge(self._clock())
        return len(self._data)
