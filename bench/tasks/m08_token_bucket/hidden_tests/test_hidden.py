import unittest

from ratelimit import KeyedRateLimiter, TokenBucket


class Clock:
    def __init__(self, t=50.0):
        self.t = t

    def __call__(self):
        return self.t


class TestTokenBucket(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()

    def test_starts_full(self):
        b = TokenBucket(1, 5, clock=self.clock)
        self.assertAlmostEqual(b.tokens, 5)
        for _ in range(5):
            self.assertTrue(b.try_acquire())
        self.assertFalse(b.try_acquire())

    def test_refill_continuous_and_fractional(self):
        b = TokenBucket(2, 10, clock=self.clock)
        self.assertTrue(b.try_acquire(10))
        self.clock.t += 0.25
        self.assertAlmostEqual(b.tokens, 0.5)
        self.assertFalse(b.try_acquire())
        self.clock.t += 0.25
        self.assertTrue(b.try_acquire())
        self.assertAlmostEqual(b.tokens, 0.0)

    def test_refill_capped(self):
        b = TokenBucket(5, 3, clock=self.clock)
        b.try_acquire(3)
        self.clock.t += 100
        self.assertAlmostEqual(b.tokens, 3)
        self.assertTrue(b.try_acquire(3))
        self.assertFalse(b.try_acquire())

    def test_failed_acquire_takes_nothing(self):
        b = TokenBucket(1, 5, clock=self.clock)
        b.try_acquire(3)
        self.assertFalse(b.try_acquire(3))
        self.assertAlmostEqual(b.tokens, 2)
        self.assertTrue(b.try_acquire(2))

    def test_multi_token(self):
        b = TokenBucket(1, 4, clock=self.clock)
        self.assertTrue(b.try_acquire(4))
        self.clock.t += 2
        self.assertFalse(b.try_acquire(3))
        self.clock.t += 1
        self.assertTrue(b.try_acquire(3))

    def test_fractional_rate_and_capacity(self):
        b = TokenBucket(0.5, 2.5, clock=self.clock)
        self.assertAlmostEqual(b.tokens, 2.5)
        self.assertTrue(b.try_acquire(2.5))
        self.clock.t += 2
        self.assertAlmostEqual(b.tokens, 1.0)

    def test_wait_time(self):
        b = TokenBucket(2, 4, clock=self.clock)
        self.assertEqual(b.wait_time(), 0.0)
        b.try_acquire(4)
        self.assertAlmostEqual(b.wait_time(), 0.5)
        self.assertAlmostEqual(b.wait_time(3), 1.5)
        self.clock.t += 0.5
        self.assertAlmostEqual(b.wait_time(3), 1.0)
        self.assertEqual(b.wait_time(1), 0.0)

    def test_wait_time_does_not_consume(self):
        b = TokenBucket(1, 3, clock=self.clock)
        b.wait_time(3)
        b.wait_time(2)
        self.assertAlmostEqual(b.tokens, 3)

    def test_wait_time_then_acquire_succeeds(self):
        b = TokenBucket(3, 6, clock=self.clock)
        b.try_acquire(5)
        w = b.wait_time(4)
        self.assertAlmostEqual(w, 1.0)
        self.clock.t += w
        self.assertTrue(b.try_acquire(4))

    def test_invalid_construction(self):
        for rate, cap in [(0, 5), (-1, 5), (1, 0), (1, -2)]:
            with self.subTest(rate=rate, cap=cap):
                with self.assertRaises(ValueError):
                    TokenBucket(rate, cap, clock=self.clock)

    def test_invalid_n(self):
        b = TokenBucket(1, 5, clock=self.clock)
        for n in (0, -1, 6, 5.5):
            with self.subTest(n=n):
                with self.assertRaises(ValueError):
                    b.try_acquire(n)
                with self.assertRaises(ValueError):
                    b.wait_time(n)
        self.assertTrue(b.try_acquire(5))

    def test_clock_backwards(self):
        b = TokenBucket(1, 5, clock=self.clock)
        b.try_acquire(3)
        self.clock.t -= 10
        self.assertAlmostEqual(b.tokens, 2)
        self.assertTrue(b.try_acquire(2))
        self.assertFalse(b.try_acquire(1))
        self.assertGreaterEqual(b.tokens, 0)
        self.assertGreater(b.wait_time(1), 0)

    def test_tokens_read_only(self):
        b = TokenBucket(1, 5, clock=self.clock)
        with self.assertRaises(AttributeError):
            b.tokens = 100

    def test_default_clock(self):
        b = TokenBucket(1000, 2)
        self.assertTrue(b.try_acquire(2))


class TestKeyed(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()

    def test_keys_independent(self):
        lim = KeyedRateLimiter(1, 2, clock=self.clock)
        self.assertTrue(lim.allow("a"))
        self.assertTrue(lim.allow("a"))
        self.assertFalse(lim.allow("a"))
        self.assertTrue(lim.allow("b"))
        self.assertTrue(lim.allow("b", 1))
        self.assertFalse(lim.allow("b"))
        self.clock.t += 1
        self.assertTrue(lim.allow("a"))
        self.assertFalse(lim.allow("a"))

    def test_new_key_starts_full_even_later(self):
        lim = KeyedRateLimiter(1, 3, clock=self.clock)
        lim.allow("a", 3)
        self.clock.t += 0.5
        self.assertTrue(lim.allow("late", 3))

    def test_len(self):
        lim = KeyedRateLimiter(1, 2, clock=self.clock)
        self.assertEqual(len(lim), 0)
        lim.allow("a")
        lim.allow("b")
        lim.allow("a")
        self.assertEqual(len(lim), 2)

    def test_cleanup(self):
        lim = KeyedRateLimiter(1, 4, clock=self.clock)
        lim.allow("a", 1)
        lim.allow("b", 4)
        lim.allow("c", 2)
        self.clock.t += 1
        self.assertEqual(lim.cleanup(), 1)   # only a is full again
        self.assertEqual(len(lim), 2)
        self.clock.t += 1
        self.assertEqual(lim.cleanup(), 1)   # c
        self.assertEqual(len(lim), 1)
        self.assertFalse(lim.allow("b", 4))  # b state kept (2 tokens)
        self.assertTrue(lim.allow("b", 2))
        self.clock.t += 10
        self.assertEqual(lim.cleanup(), 1)
        self.assertEqual(len(lim), 0)
        self.assertEqual(lim.cleanup(), 0)

    def test_n_validation(self):
        lim = KeyedRateLimiter(1, 2, clock=self.clock)
        with self.assertRaises(ValueError):
            lim.allow("a", 3)


if __name__ == "__main__":
    unittest.main()
