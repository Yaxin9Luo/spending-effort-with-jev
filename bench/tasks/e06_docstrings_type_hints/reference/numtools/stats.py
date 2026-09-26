import math
from collections.abc import Sequence


def _require_values(values, name):
    if not values:
        raise ValueError(f"{name}() of empty sequence")


def mean(values: Sequence[float]) -> float:
    """Return the arithmetic mean of values. Raises ValueError if empty."""
    _require_values(values, "mean")
    return sum(values) / len(values)


def median(values: Sequence[float]) -> float:
    """Return the median of values. Raises ValueError if empty."""
    _require_values(values, "median")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def stdev(values: Sequence[float], sample: bool = True) -> float:
    """Return the standard deviation of values.

    Uses the sample (n - 1) formula by default, or the population formula
    when sample is False. Raises ValueError with fewer than two values.
    """
    n = len(values)
    if n < 2:
        raise ValueError("stdev() needs at least two values")
    m = mean(values)
    ss = sum((v - m) ** 2 for v in values)
    return math.sqrt(ss / (n - 1 if sample else n))


def clamp(x: float, lo: float, hi: float) -> float:
    """Limit x to the range [lo, hi]. Raises ValueError if lo > hi."""
    if lo > hi:
        raise ValueError("lo must be <= hi")
    return max(lo, min(hi, x))


def normalize(values: Sequence[float]) -> list[float]:
    """Scale values so they sum to 1; all zeros if the total is 0."""
    total = sum(values)
    if total == 0:
        return [0.0 for _ in values]
    return [v / total for v in values]


def word_lengths(text: str) -> list[int]:
    """Return the length of each whitespace-separated word in text."""
    return [len(w) for w in text.split()]
