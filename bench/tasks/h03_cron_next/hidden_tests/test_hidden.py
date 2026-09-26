"""Hidden tests for h03_cron_next (crontab(5) semantics)."""
import unittest
from datetime import datetime

from cronnext import next_run


def dt(s):
    return datetime.fromisoformat(s)


class Base(unittest.TestCase):
    def nxt(self, expr, after, expected):
        got = next_run(expr, dt(after))
        self.assertEqual(got, dt(expected), f"{expr!r} after {after}")


class TestBasics(Base):
    def test_every_minute_is_strictly_after(self):
        self.nxt("* * * * *", "2025-01-01 10:00:00", "2025-01-01 10:01:00")

    def test_seconds_are_rounded_up_to_next_minute(self):
        self.nxt("* * * * *", "2025-01-01 10:00:30", "2025-01-01 10:01:00")
        self.nxt("30 10 * * *", "2025-01-01 10:30:00.500000", "2025-01-02 10:30:00")

    def test_result_has_no_seconds(self):
        got = next_run("*/5 * * * *", dt("2025-01-01 10:02:59.999999"))
        self.assertEqual((got.second, got.microsecond), (0, 0))
        self.assertEqual(got, dt("2025-01-01 10:05:00"))

    def test_lists(self):
        self.nxt("5,35 9,17 * * *", "2025-01-01 09:35:00", "2025-01-01 17:05:00")

    def test_extra_whitespace(self):
        self.nxt("  0   12 * *\t*  ", "2025-01-01 12:00:00", "2025-01-02 12:00:00")


class TestSteps(Base):
    def test_star_step_minutes(self):
        self.nxt("*/15 * * * *", "2025-01-01 10:07:00", "2025-01-01 10:15:00")
        self.nxt("*/15 * * * *", "2025-01-01 10:45:00", "2025-01-01 11:00:00")

    def test_step_not_dividing_range(self):
        self.nxt("*/40 * * * *", "2025-01-01 10:41:00", "2025-01-01 11:00:00")

    def test_range_step(self):
        self.nxt("10-50/20 * * * *", "2025-01-01 10:31:00", "2025-01-01 10:50:00")
        self.nxt("10-50/20 * * * *", "2025-01-01 10:50:00", "2025-01-01 11:10:00")
        self.nxt("5-59/15 * * * *", "2025-01-01 10:50:00", "2025-01-01 11:05:00")

    def test_hour_step_wraps_to_next_day(self):
        self.nxt("0 */5 * * *", "2025-01-01 21:00:00", "2025-01-02 00:00:00")

    def test_day_of_month_step_starts_at_1(self):
        self.nxt("0 0 */7 * *", "2025-01-01 00:00:00", "2025-01-08 00:00:00")
        self.nxt("0 0 */7 * *", "2025-01-29 00:00:00", "2025-02-01 00:00:00")

    def test_month_step_starts_at_1(self):
        self.nxt("0 0 1 */2 *", "2025-01-15 00:00:00", "2025-03-01 00:00:00")


class TestCalendar(Base):
    def test_year_rollover(self):
        self.nxt("0 0 1 1 *", "2025-12-31 23:59:00", "2026-01-01 00:00:00")
        self.nxt("59 23 31 12 *", "2025-12-31 23:59:00", "2026-12-31 23:59:00")

    def test_skips_months_without_the_day(self):
        self.nxt("0 9 31 * *", "2025-04-01 00:00:00", "2025-05-31 09:00:00")
        self.nxt("30 23 28-31 * *", "2025-02-28 23:30:00", "2025-03-28 23:30:00")

    def test_leap_day(self):
        self.nxt("0 0 29 2 *", "2025-03-01 00:00:00", "2028-02-29 00:00:00")

    def test_leap_day_across_non_leap_century(self):
        self.nxt("0 0 29 2 *", "2096-03-01 00:00:00", "2104-02-29 00:00:00")

    def test_never_fires_raises(self):
        for expr in ("0 0 30 2 *", "0 0 31 4,6,9,11 *"):
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    next_run(expr, dt("2025-01-01 00:00:00"))


class TestDayOfWeek(Base):
    def test_day_of_week_only(self):
        self.nxt("0 12 * * 1", "2025-01-01 00:00:00", "2025-01-06 12:00:00")

    def test_sunday_is_0_and_7(self):
        self.nxt("0 0 * * 0", "2025-01-01 00:00:00", "2025-01-05 00:00:00")
        self.nxt("0 0 * * 7", "2025-01-01 00:00:00", "2025-01-05 00:00:00")

    def test_range_ending_in_7(self):
        self.nxt("0 0 * * 6-7", "2025-01-04 00:00:00", "2025-01-05 00:00:00")
        self.nxt("0 0 * * 6-7", "2025-01-05 00:00:00", "2025-01-11 00:00:00")

    def test_names_case_insensitive(self):
        self.nxt("0 0 * * MON", "2025-01-01 00:00:00", "2025-01-06 00:00:00")
        self.nxt("0 0 * * fri", "2025-01-01 00:00:00", "2025-01-03 00:00:00")
        self.nxt("0 0 1 Jul *", "2025-01-01 00:00:00", "2025-07-01 00:00:00")

    def test_dom_and_dow_both_restricted_means_either(self):
        self.nxt("0 0 13 * 5", "2025-07-01 00:00:00", "2025-07-04 00:00:00")
        self.nxt("0 0 13 * 5", "2025-07-12 00:00:00", "2025-07-13 00:00:00")

    def test_either_rule_still_respects_month(self):
        self.nxt("0 0 1 2 1", "2025-01-01 00:00:00", "2025-02-01 00:00:00")
        self.nxt("0 0 1 2 1", "2025-02-01 00:00:00", "2025-02-03 00:00:00")

    def test_impossible_dom_rescued_by_dow(self):
        self.nxt("0 0 30 2 1", "2025-03-01 00:00:00", "2026-02-02 00:00:00")

    def test_dom_only_when_dow_is_star(self):
        self.nxt("0 12 15 * *", "2025-01-15 12:00:00", "2025-02-15 12:00:00")


class TestNicknames(Base):
    def test_hourly_daily(self):
        self.nxt("@hourly", "2025-01-01 10:30:00", "2025-01-01 11:00:00")
        self.nxt("@daily", "2025-01-01 10:30:00", "2025-01-02 00:00:00")
        self.nxt("@midnight", "2025-01-01 10:30:00", "2025-01-02 00:00:00")

    def test_weekly_monthly_yearly(self):
        self.nxt("@weekly", "2025-01-01 10:30:00", "2025-01-05 00:00:00")
        self.nxt("@monthly", "2025-01-01 10:30:00", "2025-02-01 00:00:00")
        self.nxt("@yearly", "2025-01-01 10:30:00", "2026-01-01 00:00:00")
        self.nxt("@annually", "2025-01-01 00:00:00", "2026-01-01 00:00:00")


class TestInvalid(unittest.TestCase):
    def test_out_of_range_values(self):
        for expr in ("60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *",
                     "* * * 0 *", "* * * 13 *", "* * * * 8"):
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    next_run(expr, dt("2025-01-01 00:00:00"))

    def test_wrong_field_count_and_garbage(self):
        for expr in ("* * * *", "* * * * * *", "", "abc * * * *", "@reboot", "@fortnightly"):
            with self.subTest(expr=expr):
                with self.assertRaises(ValueError):
                    next_run(expr, dt("2025-01-01 00:00:00"))


if __name__ == "__main__":
    unittest.main()
