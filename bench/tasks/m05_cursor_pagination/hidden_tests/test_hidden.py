import json
import unittest
from urllib.parse import parse_qs, urlsplit

from api_client import ApiError, Client


class FakeServer:
    """Serves a fixed list of pages. pages[i] is (items, next_cursor);
    next_cursor may be the sentinel MISSING to omit the key."""

    MISSING = object()

    def __init__(self, pages, failures=None):
        self.pages = pages
        self.requests = []
        self.failures = list(failures or [])  # statuses to return before real answers

    def __call__(self, method, url):
        parts = urlsplit(url)
        q = {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        self.requests.append((method, parts.path, q))
        if self.failures:
            return self.failures.pop(0), "try later"
        idx = 0 if "cursor" not in q else int(q["cursor"].lstrip("c"))
        items, nxt = self.pages[idx]
        body = {"items": items}
        if nxt is not self.MISSING:
            body["next_cursor"] = nxt
        return 200, json.dumps(body)


def paged(n_pages, per_page):
    pages = []
    k = 0
    for i in range(n_pages):
        items = [{"id": k + j} for j in range(per_page)]
        k += per_page
        pages.append((items, f"c{i + 1}" if i + 1 < n_pages else None))
    return pages


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, s):
        self.calls.append(s)


def client(server, sleep=None):
    return Client("https://api.example.com/", server, sleep=sleep or Recorder())


class TestPagination(unittest.TestCase):
    def test_all_items_and_params(self):
        srv = FakeServer(paged(3, 2))
        items = list(client(srv).iter_items("/items", page_size=2))
        self.assertEqual([i["id"] for i in items], [0, 1, 2, 3, 4, 5])
        self.assertEqual(len(srv.requests), 3)
        self.assertEqual(srv.requests[0], ("GET", "/items", {"page_size": "2"}))
        self.assertEqual(srv.requests[1][2], {"page_size": "2", "cursor": "c1"})
        self.assertEqual(srv.requests[2][2], {"page_size": "2", "cursor": "c2"})

    def test_default_page_size(self):
        srv = FakeServer([([1], None)])
        self.assertEqual(list(client(srv).iter_items("/things")), [1])
        self.assertEqual(srv.requests[0][2], {"page_size": "100"})

    def test_missing_next_cursor_ends(self):
        srv = FakeServer([([1, 2], FakeServer.MISSING)])
        self.assertEqual(list(client(srv).iter_items("/x")), [1, 2])
        self.assertEqual(len(srv.requests), 1)

    def test_empty_string_cursor_ends(self):
        srv = FakeServer([([1], "")])
        self.assertEqual(list(client(srv).iter_items("/x")), [1])
        self.assertEqual(len(srv.requests), 1)

    def test_empty_pages_are_skipped_over(self):
        srv = FakeServer([([], "c1"), ([], "c2"), (["a"], "c3"), ([], None)])
        self.assertEqual(list(client(srv).iter_items("/x")), ["a"])
        self.assertEqual(len(srv.requests), 4)

    def test_empty_endpoint(self):
        srv = FakeServer([([], None)])
        self.assertEqual(list(client(srv).iter_items("/x")), [])

    def test_lazy(self):
        srv = FakeServer(paged(3, 2))
        it = client(srv).iter_items("/x", page_size=2)
        self.assertEqual(len(srv.requests), 0)
        next(it)
        self.assertEqual(len(srv.requests), 1)
        next(it)
        self.assertEqual(len(srv.requests), 1)
        next(it)
        self.assertEqual(len(srv.requests), 2)

    def test_limit_stops_without_extra_requests(self):
        srv = FakeServer(paged(5, 2))
        items = list(client(srv).iter_items("/x", page_size=2, limit=5))
        self.assertEqual([i["id"] for i in items], [0, 1, 2, 3, 4])
        self.assertEqual(len(srv.requests), 3)

    def test_limit_on_page_boundary(self):
        srv = FakeServer(paged(5, 2))
        items = list(client(srv).iter_items("/x", page_size=2, limit=4))
        self.assertEqual(len(items), 4)
        self.assertEqual(len(srv.requests), 2)

    def test_limit_larger_than_total(self):
        srv = FakeServer(paged(2, 3))
        self.assertEqual(len(list(client(srv).iter_items("/x", limit=100))), 6)

    def test_limit_zero(self):
        srv = FakeServer(paged(2, 3))
        self.assertEqual(list(client(srv).iter_items("/x", limit=0)), [])
        self.assertEqual(srv.requests, [])

    def test_repeated_cursor_raises(self):
        srv = FakeServer([([1], "c1"), ([2], "c2"), ([3], "c1")])
        got = []
        with self.assertRaises(ApiError):
            for item in client(srv).iter_items("/x"):
                got.append(item)
                if len(got) > 50:
                    self.fail("looped")
        self.assertEqual(got, [1, 2, 3])

    def test_self_referencing_cursor_raises(self):
        srv = FakeServer([([1], "c1"), ([2], "c1")])
        with self.assertRaises(ApiError):
            for i, _ in enumerate(client(srv).iter_items("/x")):
                if i > 50:
                    self.fail("looped")

    def test_existing_method_still_works(self):
        c = Client("https://h/", lambda m, u: (200, json.dumps({"id": 7, "url": u})))
        self.assertEqual(c.get_item(7)["url"], "https://h/items/7")


class TestRetry(unittest.TestCase):
    def test_retry_then_success(self):
        srv = FakeServer(paged(1, 2), failures=[503, 429])
        sleep = Recorder()
        items = list(client(srv, sleep).iter_items("/x"))
        self.assertEqual(len(items), 2)
        self.assertEqual(sleep.calls, [0.5, 1.0])
        self.assertEqual(len(srv.requests), 3)
        self.assertEqual(srv.requests[0][2], srv.requests[2][2])

    def test_retries_exhausted(self):
        srv = FakeServer(paged(1, 2), failures=[500, 502, 503, 504])
        sleep = Recorder()
        with self.assertRaises(ApiError) as cm:
            list(client(srv, sleep).iter_items("/x", retries=2))
        self.assertEqual(cm.exception.status, 503)
        self.assertEqual(len(srv.requests), 3)
        self.assertEqual(sleep.calls, [0.5, 1.0])

    def test_custom_retries_doubling(self):
        srv = FakeServer(paged(1, 1), failures=[500, 500, 500])
        sleep = Recorder()
        self.assertEqual(len(list(client(srv, sleep).iter_items("/x", retries=3))), 1)
        self.assertEqual(sleep.calls, [0.5, 1.0, 2.0])

    def test_zero_retries(self):
        srv = FakeServer(paged(1, 1), failures=[503])
        sleep = Recorder()
        with self.assertRaises(ApiError):
            list(client(srv, sleep).iter_items("/x", retries=0))
        self.assertEqual(sleep.calls, [])

    def test_non_retryable_propagates(self):
        srv = FakeServer(paged(1, 1), failures=[404])
        sleep = Recorder()
        with self.assertRaises(ApiError) as cm:
            list(client(srv, sleep).iter_items("/x"))
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual(len(srv.requests), 1)
        self.assertEqual(sleep.calls, [])

    def test_retry_budget_is_per_request(self):
        pages = paged(3, 1)

        class Srv(FakeServer):
            def __call__(self, method, url):
                n = len(self.requests)
                # fail twice before each page: requests 0,1 fail, 2 ok, 3,4 fail, 5 ok, ...
                if n % 3 != 2:
                    self.requests.append((method, url, None))
                    return 503, "busy"
                return FakeServer.__call__(self, method, url)

        srv = Srv(pages)
        sleep = Recorder()
        items = list(client(srv, sleep).iter_items("/x", retries=2))
        self.assertEqual(len(items), 3)
        self.assertEqual(sleep.calls, [0.5, 1.0] * 3)

    def test_retry_on_later_page_keeps_cursor(self):
        srv = FakeServer(paged(2, 1))
        orig = srv.__call__
        state = {"n": 0}

        def transport(method, url):
            state["n"] += 1
            if state["n"] == 2:
                srv.requests.append(("GET", "fail", {}))
                return 500, "oops"
            return orig(method, url)

        items = list(Client("https://h", transport, sleep=Recorder()).iter_items("/x"))
        self.assertEqual(len(items), 2)
        self.assertEqual(srv.requests[-1][2].get("cursor"), "c1")


class TestValidation(unittest.TestCase):
    def check(self, **kwargs):
        srv = FakeServer(paged(1, 1))
        with self.assertRaises(ValueError):
            list(client(srv).iter_items("/x", **kwargs))

    def test_bad_args(self):
        self.check(page_size=0)
        self.check(limit=-1)
        self.check(retries=-1)


if __name__ == "__main__":
    unittest.main()
