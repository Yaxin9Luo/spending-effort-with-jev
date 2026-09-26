import unittest
from datetime import datetime, timedelta

from scheduler.intervals import Interval, clip, merge, overlaps
from scheduler.slots import find_conflicts, format_slots, free_slots, total_busy


def t(hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime(2025, 3, 10, h, m)


def iv(a, b):
    return Interval(t(a), t(b))


class TestIntervals(unittest.TestCase):
    def test_overlaps(self):
        self.assertTrue(overlaps(iv("09:00", "10:00"), iv("09:30", "11:00")))
        self.assertFalse(overlaps(iv("09:00", "10:00"), iv("11:00", "12:00")))

    def test_merge_overlapping(self):
        self.assertEqual(merge([iv("13:00", "14:00"), iv("09:00", "10:00"), iv("09:30", "11:00")]),
                         [iv("09:00", "11:00"), iv("13:00", "14:00")])

    def test_clip(self):
        self.assertEqual(clip(iv("08:00", "10:00"), t("09:00"), t("17:00")), iv("09:00", "10:00"))
        self.assertIsNone(clip(iv("07:00", "08:00"), t("09:00"), t("17:00")))


class TestSlots(unittest.TestCase):
    def test_free_slots(self):
        busy = [iv("10:00", "11:00"), iv("13:00", "14:30")]
        self.assertEqual(free_slots(busy, t("09:00"), t("17:00")),
                         [iv("09:00", "10:00"), iv("11:00", "13:00"), iv("14:30", "17:00")])

    def test_min_minutes(self):
        busy = [iv("10:00", "11:00"), iv("11:30", "12:00")]
        self.assertEqual(free_slots(busy, t("09:00"), t("12:00"), min_minutes=45),
                         [iv("09:00", "10:00")])

    def test_empty_busy(self):
        self.assertEqual(free_slots([], t("09:00"), t("17:00")), [iv("09:00", "17:00")])

    def test_total_busy(self):
        busy = [iv("09:00", "10:00"), iv("09:30", "10:30")]
        self.assertEqual(total_busy(busy, t("08:00"), t("18:00")), timedelta(minutes=90))

    def test_conflicts(self):
        bookings = [iv("09:00", "10:00"), iv("09:30", "10:30"), iv("11:00", "12:00")]
        self.assertEqual(find_conflicts(bookings), [(0, 1)])

    def test_format(self):
        self.assertEqual(format_slots([iv("09:00", "10:30")]), "09:00-10:30")


if __name__ == "__main__":
    unittest.main()
