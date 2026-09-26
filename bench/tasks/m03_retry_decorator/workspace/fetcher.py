"""Example caller; will use retry() once it exists."""
import urllib.request


def fetch(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()
