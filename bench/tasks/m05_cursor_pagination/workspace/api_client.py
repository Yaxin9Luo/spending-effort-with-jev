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
