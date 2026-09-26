"""Hidden tests for h06_free_slots."""
import random
import unittest
from datetime import datetime, timedelta

from scheduler.intervals import Interval, merge, overlaps
from scheduler.slots import find_conflicts, format_slots, free_slots, total_busy

DAY = datetime(2025, 3, 10)


def t(hhmm):
    h, m = map(int, hhmm.split(":"))
    return DAY + timedelta(hours=h, minutes=m)


def iv(a, b):
    return Interval(t(a), t(b))


def m(minute):
    return DAY + timedelta(minutes=minute)


def brute_free(busy_minutes, lo, hi, min_minutes):
    """Free runs on a minute grid."""
    taken = set()
    for a, b in busy_minutes:
        taken.update(range(a, b))
    runs, start = [], None
    for x in range(lo, hi + 1):
        free = x < hi and x not in taken
        if free and start is None:
            start = x
        elif not free and start is not None:
            runs.append((start, x))
            start = None
    return [Interval(m(a), m(b)) for a, b in runs if b - a >= min_minutes]


def brute_merge(busy_minutes):
    taken = set()
    for a, b in busy_minutes:
        taken.update(range(a, b))
    runs, start = [], None
    for x in range(0, 30 * 60 + 1):
        inside = x in taken
        if inside and start is None:
            start = x
        elif not inside and start is not None:
            runs.append(Interval(m(start), m(x)))
            start = None
    return runs


def random_busy(rng):
    out = []
    for _ in range(rng.randint(0, 8)):
        a = rng.randrange(6 * 60, 20 * 60, 15)
        length = rng.choice([0, 15, 30, 60, 90, 180, 300])
        out.append((a, a + length))
    return out


class TestReportedBugs(unittest.TestCase):
    def test_back_to_back_meetings_no_zero_length_slot(self):
        busy = [iv("09:00", "10:00"), iv("10:00", "11:00")]
        self.assertEqual(free_slots(busy, t("09:00"), t("12:00")), [iv("11:00", "12:00")])

    def test_meeting_inside_workshop(self):
        busy = [iv("08:00", "12:00"), iv("09:00", "10:00")]
        self.assertEqual(free_slots(busy, t("08:00"), t("17:00")), [iv("12:00", "17:00")])

    def test_several_nested_unsorted(self):
        busy = [iv("12:00", "13:00"), iv("09:00", "17:00"), iv("10:00", "11:00")]
        self.assertEqual(free_slots(busy, t("08:00"), t("18:00")),
                         [iv("08:00", "09:00"), iv("17:00", "18:00")])

    def test_formatted_output(self):
        busy = [iv("09:00", "10:00"), iv("10:00", "11:00"), iv("13:00", "14:00")]
        self.assertEqual(format_slots(free_slots(busy, t("09:00"), t("15:00"))),
                         "11:00-13:00, 14:00-15:00")


class TestMerge(unittest.TestCase):
    def test_touching_are_combined(self):
        self.assertEqual(merge([iv("09:00", "10:00"), iv("10:00", "11:00")]), [iv("09:00", "11:00")])

    def test_contained_interval_keeps_outer_end(self):
        self.assertEqual(merge([iv("09:00", "12:00"), iv("10:00", "11:00")]), [iv("09:00", "12:00")])

    def test_chain_unsorted_with_duplicates(self):
        ivs = [iv("11:00", "11:30"), iv("09:00", "10:00"), iv("09:00", "10:00"),
               iv("10:00", "10:15"), iv("09:30", "09:45"), iv("14:00", "15:00")]
        self.assertEqual(merge(ivs), [iv("09:00", "10:15"), iv("11:00", "11:30"), iv("14:00", "15:00")])

    def test_zero_length_dropped(self):
        self.assertEqual(merge([iv("09:00", "10:00"), iv("12:00", "12:00")]), [iv("09:00", "10:00")])
        self.assertEqual(merge([iv("10:00", "10:00"), iv("09:00", "10:00"), iv("10:00", "11:00")]),
                         [iv("09:00", "11:00")])
        self.assertEqual(merge([iv("10:00", "10:00")]), [])

    def test_does_not_modify_input(self):
        ivs = [iv("10:00", "11:00"), iv("09:00", "12:00")]
        before = list(ivs)
        merge(ivs)
        self.assertEqual(ivs, before)

    def test_reversed_interval_rejected(self):
        with self.assertRaises(ValueError):
            merge([iv("10:00", "09:00")])

    def test_random_against_minute_grid(self):
        rng = random.Random(42)
        for _ in range(400):
            busy = random_busy(rng)
            with self.subTest(busy=busy):
                got = merge([Interval(m(a), m(b)) for a, b in busy])
                self.assertEqual(got, brute_merge(busy))
                for x, y in zip(got, got[1:]):
                    self.assertGreater(y.start, x.end)


class TestFreeSlots(unittest.TestCase):
    def test_min_minutes_is_inclusive(self):
        busy = [iv("09:30", "10:00"), iv("10:30", "11:00")]
        self.assertEqual(free_slots(busy, t("09:00"), t("11:00"), min_minutes=30),
                         [iv("09:00", "09:30"), iv("10:00", "10:30")])
        self.assertEqual(free_slots(busy, t("09:00"), t("11:00"), min_minutes=31), [])

    def test_busy_outside_window_is_clipped(self):
        busy = [iv("07:00", "09:30"), iv("16:30", "19:00")]
        self.assertEqual(free_slots(busy, t("09:00"), t("17:00")), [iv("09:30", "16:30")])

    def test_busy_entirely_outside_window(self):
        busy = [iv("06:00", "07:00"), iv("18:00", "19:00"), iv("07:00", "09:00")]
        self.assertEqual(free_slots(busy, t("09:00"), t("17:00")), [iv("09:00", "17:00")])

    def test_fully_booked(self):
        busy = [iv("08:00", "13:00"), iv("12:00", "18:00")]
        self.assertEqual(free_slots(busy, t("09:00"), t("17:00")), [])

    def test_plain_tuples_accepted(self):
        busy = [(t("10:00"), t("11:00")), (t("10:30"), t("10:45"))]
        self.assertEqual(free_slots(busy, t("09:00"), t("12:00")),
                         [iv("09:00", "10:00"), iv("11:00", "12:00")])

    def test_invalid_window(self):
        with self.assertRaises(ValueError):
            free_slots([], t("10:00"), t("10:00"))

    def test_random_against_minute_grid(self):
        rng = random.Random(7)
        for _ in range(400):
            busy = random_busy(rng)
            lo = rng.randrange(5 * 60, 12 * 60, 15)
            hi = rng.randrange(13 * 60, 23 * 60, 15)
            min_minutes = rng.choice([0, 0, 15, 30, 60])
            with self.subTest(busy=busy, lo=lo, hi=hi, min_minutes=min_minutes):
                got = free_slots([(m(a), m(b)) for a, b in busy], m(lo), m(hi), min_minutes)
                self.assertEqual(got, brute_free(busy, lo, hi, min_minutes))


class TestTotalBusy(unittest.TestCase):
    def test_nested(self):
        busy = [iv("09:00", "12:00"), iv("10:00", "11:00")]
        self.assertEqual(total_busy(busy, t("08:00"), t("18:00")), timedelta(hours=3))

    def test_random_against_minute_grid(self):
        rng = random.Random(3)
        for _ in range(300):
            busy = random_busy(rng)
            with self.subTest(busy=busy):
                taken = set()
                for a, b in busy:
                    taken.update(x for x in range(a, b) if 8 * 60 <= x < 18 * 60)
                got = total_busy([(m(a), m(b)) for a, b in busy], t("08:00"), t("18:00"))
                self.assertEqual(got, timedelta(minutes=len(taken)))


class TestConflicts(unittest.TestCase):
    def test_back_to_back_is_not_a_conflict(self):
        self.assertEqual(find_conflicts([iv("09:00", "10:00"), iv("10:00", "11:00")]), [])

    def test_overlaps_touching_is_false(self):
        self.assertFalse(overlaps(iv("09:00", "10:00"), iv("10:00", "11:00")))

    def test_nested_and_identical(self):
        bookings = [iv("09:00", "12:00"), iv("10:00", "11:00"), iv("12:00", "13:00"), iv("12:00", "13:00")]
        self.assertEqual(find_conflicts(bookings), [(0, 1), (2, 3)])


if __name__ == "__main__":
    unittest.main()
