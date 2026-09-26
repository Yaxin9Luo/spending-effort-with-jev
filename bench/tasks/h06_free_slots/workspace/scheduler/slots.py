"""Free/busy calculations for a single room or person."""
from datetime import timedelta

from .intervals import Interval, clip, merge, overlaps


def _window_busy(busy, window_start, window_end):
    if window_start >= window_end:
        raise ValueError("window must have positive length")
    clipped = (clip(Interval(*b), window_start, window_end) for b in busy)
    return merge(c for c in clipped if c is not None)


def free_slots(busy, window_start, window_end, min_minutes=0):
    """Return the free time inside [window_start, window_end) as a sorted list of Intervals.

    busy        -- iterable of (start, end) pairs (Intervals or tuples), in any
                   order, possibly overlapping, possibly extending outside the
                   window
    min_minutes -- only return slots at least this many minutes long (a slot
                   of exactly min_minutes is kept)

    Every returned slot has positive length and lies entirely inside the window.
    """
    merged = _window_busy(busy, window_start, window_end)
    if not merged:
        gaps = [Interval(window_start, window_end)]
    else:
        gaps = []
        if merged[0].start > window_start:
            gaps.append(Interval(window_start, merged[0].start))
        for prev, nxt in zip(merged, merged[1:]):
            gaps.append(Interval(prev.end, nxt.start))
        if merged[-1].end < window_end:
            gaps.append(Interval(merged[-1].end, window_end))
    min_len = timedelta(minutes=min_minutes)
    return [g for g in gaps if g.end - g.start >= min_len]


def total_busy(busy, window_start, window_end):
    """Total busy time inside the window, as a timedelta (overlaps counted once)."""
    merged = _window_busy(busy, window_start, window_end)
    return sum((iv.end - iv.start for iv in merged), timedelta())


def find_conflicts(bookings):
    """Return (i, j) index pairs, i < j, of bookings that overlap, sorted.

    Back-to-back bookings (one ends exactly when the other starts) are not
    conflicts.
    """
    ivs = [Interval(*b) for b in bookings]
    out = []
    for i in range(len(ivs)):
        for j in range(i + 1, len(ivs)):
            if overlaps(ivs[i], ivs[j]):
                out.append((i, j))
    return out


def format_slots(slots):
    """Human-readable list like '09:00-10:30, 13:00-17:00'."""
    return ", ".join(f"{s.start:%H:%M}-{s.end:%H:%M}" for s in slots)
