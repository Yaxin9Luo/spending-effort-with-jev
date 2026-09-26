"""In-memory cache used by the web layer (see TTLCache)."""


class TTLCache:
    """LRU cache with per-entry expiry. Not implemented yet."""

    def __init__(self, maxsize, ttl=None, clock=None):
        raise NotImplementedError
