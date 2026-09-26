import unittest

from ttlcache import TTLCache


class Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


class TestBasics(unittest.TestCase):
    def setUp(self):
        self.clock = Clock(100.0)

    def test_set_get_and_default(self):
        c = TTLCache(3, clock=self.clock)
        c.set("a", 1)
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("missing"))
        self.assertEqual(c.get("missing", "d"), "d")

    def test_stores_falsy_values(self):
        c = TTLCache(3, clock=self.clock)
        c.set("z", 0)
        c.set("n", None)
        self.assertEqual(c.get("z", "d"), 0)
        self.assertIn("n", c)

    def test_lru_eviction(self):
        c = TTLCache(2, clock=self.clock)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        self.assertNotIn("a", c)
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)
        self.assertEqual(len(c), 2)

    def test_get_refreshes_recency(self):
        c = TTLCache(2, clock=self.clock)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")
        c.set("c", 3)
        self.assertIn("a", c)
        self.assertNotIn("b", c)

    def test_contains_does_not_refresh_recency(self):
        c = TTLCache(2, clock=self.clock)
        c.set("a", 1)
        c.set("b", 2)
        self.assertTrue("a" in c)
        c.set("c", 3)
        self.assertNotIn("a", c)
        self.assertIn("b", c)

    def test_overwrite_refreshes_and_does_not_evict(self):
        c = TTLCache(2, clock=self.clock)
        c.set("a", 1)
        c.set("b", 2)
        c.set("a", 10)
        self.assertEqual(len(c), 2)
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("a"), 10)
        c2 = TTLCache(2, clock=self.clock)
        c2.set("a", 1)
        c2.set("b", 2)
        c2.set("a", 3)
        c2.set("c", 4)
        self.assertNotIn("b", c2)
        self.assertEqual(c2.get("a"), 3)

    def test_delete(self):
        c = TTLCache(2, clock=self.clock)
        c.set("a", 1)
        self.assertTrue(c.delete("a"))
        self.assertFalse(c.delete("a"))
        self.assertFalse(c.delete("never"))
        self.assertEqual(len(c), 0)


class TestExpiry(unittest.TestCase):
    def setUp(self):
        self.clock = Clock(1000.0)

    def test_default_ttl_boundary(self):
        c = TTLCache(5, ttl=10, clock=self.clock)
        c.set("a", 1)
        self.clock.t = 1009.999
        self.assertEqual(c.get("a"), 1)
        self.clock.t = 1010.0
        self.assertIsNone(c.get("a"))
        self.assertNotIn("a", c)

    def test_no_ttl_never_expires(self):
        c = TTLCache(5, clock=self.clock)
        c.set("a", 1)
        self.clock.t += 10 ** 9
        self.assertEqual(c.get("a"), 1)

    def test_per_call_ttl_overrides_default(self):
        c = TTLCache(5, ttl=100, clock=self.clock)
        c.set("short", 1, ttl=5)
        c.set("default", 2)
        self.clock.t += 5
        self.assertNotIn("short", c)
        self.assertIn("default", c)
        self.clock.t += 95
        self.assertNotIn("default", c)

    def test_per_call_ttl_without_default(self):
        c = TTLCache(5, clock=self.clock)
        c.set("a", 1, ttl=3)
        c.set("b", 2)
        self.clock.t += 3
        self.assertNotIn("a", c)
        self.assertIn("b", c)

    def test_overwrite_restarts_expiry(self):
        c = TTLCache(5, ttl=10, clock=self.clock)
        c.set("a", 1)
        self.clock.t += 8
        c.set("a", 2)
        self.clock.t += 8
        self.assertEqual(c.get("a"), 2)

    def test_len_counts_only_live(self):
        c = TTLCache(5, ttl=10, clock=self.clock)
        c.set("a", 1)
        c.set("b", 2, ttl=100)
        self.assertEqual(len(c), 2)
        self.clock.t += 10
        self.assertEqual(len(c), 1)

    def test_delete_expired_returns_false(self):
        c = TTLCache(5, ttl=10, clock=self.clock)
        c.set("a", 1)
        self.clock.t += 10
        self.assertFalse(c.delete("a"))

    def test_expired_entries_dropped_before_lru_eviction(self):
        c = TTLCache(2, clock=self.clock)
        c.set("b", 2)            # no expiry, will be least recently used
        c.set("a", 1, ttl=10)
        c.get("a")               # a is most recently used
        self.clock.t += 10       # a expires
        c.set("c", 3)
        self.assertIn("b", c)
        self.assertIn("c", c)
        self.assertNotIn("a", c)

    def test_expired_key_reinsert_counts_as_new(self):
        c = TTLCache(2, clock=self.clock)
        c.set("a", 1, ttl=5)
        c.set("b", 2)
        self.clock.t += 5
        c.set("a", 9)
        self.assertEqual(c.get("a"), 9)
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(len(c), 2)


class TestValidation(unittest.TestCase):
    def test_bad_maxsize(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                TTLCache(bad)

    def test_bad_default_ttl(self):
        for bad in (0, -5):
            with self.assertRaises(ValueError):
                TTLCache(3, ttl=bad)

    def test_bad_per_call_ttl(self):
        c = TTLCache(3, clock=Clock())
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                c.set("a", 1, ttl=bad)

    def test_default_clock_works(self):
        c = TTLCache(2, ttl=60)
        c.set("a", 1)
        self.assertEqual(c.get("a"), 1)


if __name__ == "__main__":
    unittest.main()
