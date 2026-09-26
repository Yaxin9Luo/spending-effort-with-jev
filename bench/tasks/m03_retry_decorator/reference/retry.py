"""Retry helpers."""
import asyncio
import functools
import inspect
import time


def retry(attempts=3, exceptions=(Exception,), delay=0.0, backoff=2.0,
          max_delay=None, sleep=None, on_retry=None):
    """Retry the decorated function when it raises one of `exceptions`."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")
    if backoff < 1:
        raise ValueError("backoff must be >= 1")
    if max_delay is not None and max_delay < 0:
        raise ValueError("max_delay must be >= 0")
    if isinstance(exceptions, type):
        exceptions = (exceptions,)
    else:
        exceptions = tuple(exceptions)

    def wait_for(k):
        w = delay * backoff ** (k - 1)
        if max_delay is not None:
            w = min(w, max_delay)
        return w

    def decorate(func):
        if inspect.iscoroutinefunction(func):
            do_sleep = sleep if sleep is not None else asyncio.sleep

            @functools.wraps(func)
            async def awrapper(*args, **kwargs):
                for attempt in range(1, attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        if attempt == attempts:
                            raise
                        w = wait_for(attempt)
                        if on_retry is not None:
                            on_retry(attempt, exc, w)
                        r = do_sleep(w)
                        if inspect.isawaitable(r):
                            await r
            return awrapper

        do_sleep = sleep if sleep is not None else time.sleep

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts:
                        raise
                    w = wait_for(attempt)
                    if on_retry is not None:
                        on_retry(attempt, exc, w)
                    do_sleep(w)
        return wrapper

    return decorate
