"""Half-open time intervals [start, end)."""
from collections import namedtuple

Interval = namedtuple("Interval", "start end")


def overlaps(a, b):
    """True if intervals a and b share any time.

    Intervals are half-open, so ones that merely touch (a.end == b.start)
    do NOT overlap.
    """
    return a.start < b.end and b.start < a.end


def merge(intervals):
    """Merge a collection of intervals into a sorted list of disjoint intervals.

    Overlapping intervals and intervals that touch (one ends exactly when the
    next starts) are combined into one. Zero-length intervals (start == end)
    are dropped. The input is not modified. Consecutive intervals in the
    result are always separated by a gap of positive length.
    """
    result = []
    for iv in sorted(intervals):
        if iv.end < iv.start:
            raise ValueError(f"interval ends before it starts: {iv}")
        if result and overlaps(result[-1], iv):
            result[-1] = Interval(result[-1].start, iv.end)
        else:
            result.append(Interval(iv.start, iv.end))
    return result


def clip(iv, lo, hi):
    """Restrict interval `iv` to [lo, hi). Returns None if nothing is left."""
    start, end = max(iv.start, lo), min(iv.end, hi)
    if start >= end:
        return None
    return Interval(start, end)
