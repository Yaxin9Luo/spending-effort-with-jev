import math


def _require_values(values, name):
    if not values:
        raise ValueError(f"{name}() of empty sequence")


def mean(values):
    _require_values(values, "mean")
    return sum(values) / len(values)


def median(values):
    _require_values(values, "median")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def stdev(values, sample=True):
    n = len(values)
    if n < 2:
        raise ValueError("stdev() needs at least two values")
    m = mean(values)
    ss = sum((v - m) ** 2 for v in values)
    return math.sqrt(ss / (n - 1 if sample else n))


def clamp(x, lo, hi):
    if lo > hi:
        raise ValueError("lo must be <= hi")
    return max(lo, min(hi, x))


def normalize(values):
    total = sum(values)
    if total == 0:
        return [0.0 for _ in values]
    return [v / total for v in values]


def word_lengths(text):
    return [len(w) for w in text.split()]
