import asyncio
import inspect
import time
import unittest

from retry import retry


class Flaky:
    """Raises the given exceptions in order, then returns 'ok'."""

    def __init__(self, *errors):
        self.errors = list(errors)
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        self.last_args = (args, kwargs)
        if self.errors:
            raise self.errors.pop(0)
        return "ok"


class TestSync(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        self.sleep = self.sleeps.append

    def test_success_first_try(self):
        f = Flaky()
        g = retry(sleep=self.sleep)(f)
        self.assertEqual(g(1, x=2), "ok")
        self.assertEqual(f.calls, 1)
        self.assertEqual(f.last_args, ((1,), {"x": 2}))
        self.assertEqual(self.sleeps, [])

    def test_retries_then_succeeds_with_backoff(self):
        f = Flaky(ValueError("a"), ValueError("b"))
        g = retry(attempts=3, delay=1, backoff=2, sleep=self.sleep)(f)
        self.assertEqual(g(), "ok")
        self.assertEqual(f.calls, 3)
        self.assertEqual(self.sleeps, [1, 2])

    def test_exhausted_reraises_original(self):
        errs = [KeyError("1"), KeyError("2"), KeyError("3"), KeyError("4")]
        f = Flaky(*errs)
        g = retry(attempts=4, delay=0.5, backoff=3, sleep=self.sleep)(f)
        with self.assertRaises(KeyError) as cm:
            g()
        self.assertIs(cm.exception, errs[3])
        self.assertEqual(f.calls, 4)
        self.assertEqual(len(self.sleeps), 3)
        for got, want in zip(self.sleeps, [0.5, 1.5, 4.5]):
            self.assertAlmostEqual(got, want)

    def test_max_delay_caps(self):
        f = Flaky(*[OSError()] * 5)
        g = retry(attempts=6, delay=1, backoff=3, max_delay=5, sleep=self.sleep)(f)
        self.assertEqual(g(), "ok")
        self.assertEqual(self.sleeps, [1, 3, 5, 5, 5])

    def test_zero_delay_still_sleeps(self):
        f = Flaky(ValueError(), ValueError())
        g = retry(attempts=3, sleep=self.sleep)(f)
        self.assertEqual(g(), "ok")
        self.assertEqual(self.sleeps, [0, 0])

    def test_single_attempt(self):
        f = Flaky(ValueError())
        g = retry(attempts=1, delay=1, sleep=self.sleep)(f)
        with self.assertRaises(ValueError):
            g()
        self.assertEqual(f.calls, 1)
        self.assertEqual(self.sleeps, [])

    def test_non_matching_exception_propagates_immediately(self):
        f = Flaky(TypeError("boom"), TypeError("again"))
        g = retry(attempts=5, exceptions=(ValueError, KeyError), delay=1, sleep=self.sleep)(f)
        with self.assertRaises(TypeError):
            g()
        self.assertEqual(f.calls, 1)
        self.assertEqual(self.sleeps, [])

    def test_single_exception_class_and_subclass(self):
        f = Flaky(ConnectionResetError(), ConnectionRefusedError())
        g = retry(attempts=3, exceptions=ConnectionError, sleep=self.sleep)(f)
        self.assertEqual(g(), "ok")
        self.assertEqual(f.calls, 3)

    def test_mixed_matching_then_non_matching(self):
        f = Flaky(ValueError(), RuntimeError())
        g = retry(attempts=5, exceptions=ValueError, sleep=self.sleep)(f)
        with self.assertRaises(RuntimeError):
            g()
        self.assertEqual(f.calls, 2)
        self.assertEqual(len(self.sleeps), 1)

    def test_on_retry(self):
        e1, e2 = ValueError("1"), ValueError("2")
        f = Flaky(e1, e2, ValueError("3"))
        seen = []
        g = retry(attempts=3, delay=2, backoff=1.5, sleep=self.sleep,
                  on_retry=lambda a, e, w: seen.append((a, e, w)))(f)
        with self.assertRaises(ValueError):
            g()
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][0], 1)
        self.assertIs(seen[0][1], e1)
        self.assertAlmostEqual(seen[0][2], 2)
        self.assertEqual(seen[1][0], 2)
        self.assertIs(seen[1][1], e2)
        self.assertAlmostEqual(seen[1][2], 3)

    def test_on_retry_called_before_sleep(self):
        order = []
        f = Flaky(ValueError())
        g = retry(sleep=lambda w: order.append("sleep"),
                  on_retry=lambda a, e, w: order.append("hook"))(f)
        g()
        self.assertEqual(order, ["hook", "sleep"])

    def test_wraps(self):
        @retry(sleep=self.sleep)
        def my_func():
            """My docstring."""
            return 1
        self.assertEqual(my_func.__name__, "my_func")
        self.assertEqual(my_func.__doc__, "My docstring.")

    def test_default_sleep_really_waits(self):
        f = Flaky(ValueError())
        g = retry(delay=0.1)(f)
        t0 = time.monotonic()
        self.assertEqual(g(), "ok")
        self.assertGreaterEqual(time.monotonic() - t0, 0.08)

    def test_validation(self):
        for kwargs in ({"attempts": 0}, {"attempts": -1}, {"delay": -0.1},
                       {"backoff": 0.5}, {"max_delay": -1}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    retry(**kwargs)

    def test_backoff_one_is_constant(self):
        f = Flaky(ValueError(), ValueError(), ValueError())
        g = retry(attempts=4, delay=0.3, backoff=1, sleep=self.sleep)(f)
        g()
        self.assertEqual(self.sleeps, [0.3, 0.3, 0.3])


class AsyncFlaky(Flaky):
    async def run(self, *args, **kwargs):
        await asyncio.sleep(0)
        return Flaky.__call__(self, *args, **kwargs)


class TestAsync(unittest.TestCase):
    def test_is_coroutine_function_and_retries_with_sync_sleep(self):
        f = AsyncFlaky(ValueError(), ValueError())
        sleeps = []

        @retry(attempts=3, delay=1, backoff=2, sleep=sleeps.append)
        async def work(x):
            return await f.run(x)

        self.assertTrue(inspect.iscoroutinefunction(work))
        self.assertEqual(f.calls, 0)
        self.assertEqual(asyncio.run(work(5)), "ok")
        self.assertEqual(f.calls, 3)
        self.assertEqual(sleeps, [1, 2])

    def test_async_custom_sleep_is_awaited(self):
        f = AsyncFlaky(ValueError(), ValueError())
        slept = []

        async def fake_sleep(w):
            await asyncio.sleep(0)
            slept.append(w)

        @retry(attempts=3, delay=0.5, sleep=fake_sleep)
        async def work():
            return await f.run()

        self.assertEqual(asyncio.run(work()), "ok")
        self.assertEqual(slept, [0.5, 1.0])

    def test_async_exhausted_and_non_matching(self):
        errs = [ValueError("1"), ValueError("2")]
        f = AsyncFlaky(*errs)

        @retry(attempts=2, sleep=lambda w: None)
        async def work():
            return await f.run()

        with self.assertRaises(ValueError) as cm:
            asyncio.run(work())
        self.assertIs(cm.exception, errs[1])

        g = AsyncFlaky(TypeError())

        @retry(attempts=5, exceptions=ValueError, sleep=lambda w: None)
        async def work2():
            return await g.run()

        with self.assertRaises(TypeError):
            asyncio.run(work2())
        self.assertEqual(g.calls, 1)

    def test_async_default_sleep_does_not_block_loop(self):
        f = AsyncFlaky(ValueError())
        order = []

        @retry(attempts=2, delay=0.3)
        async def work():
            r = await f.run()
            order.append("work")
            return r

        async def ticker():
            for _ in range(5):
                await asyncio.sleep(0.01)
            order.append("ticker")

        async def main():
            return await asyncio.gather(work(), ticker())

        t0 = time.monotonic()
        res = asyncio.run(main())
        self.assertEqual(res[0], "ok")
        self.assertGreaterEqual(time.monotonic() - t0, 0.25)
        self.assertEqual(order, ["ticker", "work"])

    def test_async_wraps(self):
        @retry()
        async def named():
            """Doc."""
        self.assertEqual(named.__name__, "named")
        self.assertEqual(named.__doc__, "Doc.")


if __name__ == "__main__":
    unittest.main()
