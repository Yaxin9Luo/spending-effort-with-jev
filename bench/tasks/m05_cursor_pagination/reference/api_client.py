"""Thin client for the inventory API."""
import json
import time
from urllib.parse import urlencode


class ApiError(Exception):
    def __init__(self, status, message=""):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


class Client:
    """`transport(method, url)` performs the HTTP request and returns
    (status_code, body_text). `sleep` is injectable for tests."""

    def __init__(self, base_url, transport, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.sleep = sleep

    def _get(self, path, params=None):
        url = self.base_url + path
        if params:
            url += "?" + urlencode(params)
        status, body = self.transport("GET", url)
        if status >= 400:
            raise ApiError(status, body)
        return json.loads(body)

    def get_item(self, item_id):
        return self._get(f"/items/{item_id}")

    def _get_with_retry(self, path, params, retries):
        wait = 0.5
        for attempt in range(retries + 1):
            try:
                return self._get(path, params)
            except ApiError as e:
                retryable = e.status == 429 or 500 <= e.status <= 599
                if not retryable or attempt == retries:
                    raise
                self.sleep(wait)
                wait *= 2

    def iter_items(self, path, page_size=100, limit=None, retries=2):
        """Yield every item of a cursor-paginated list endpoint."""
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        if retries < 0:
            raise ValueError("retries must be >= 0")
        return self._iter_items(path, page_size, limit, retries)

    def _iter_items(self, path, page_size, limit, retries):
        yielded = 0
        cursor = None
        seen = set()
        while limit is None or yielded < limit:
            params = {"page_size": page_size}
            if cursor is not None:
                params["cursor"] = cursor
            page = self._get_with_retry(path, params, retries)
            for item in page.get("items") or []:
                yield item
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            nxt = page.get("next_cursor")
            if not nxt:
                return
            if nxt in seen:
                raise ApiError(0, f"pagination loop: cursor {nxt!r} repeated")
            seen.add(nxt)
            cursor = nxt
