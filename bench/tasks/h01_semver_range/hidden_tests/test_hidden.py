"""Hidden tests for h01_semver_range. Expected values were checked against node-semver."""
import unittest

from semverlite import max_satisfying, satisfies


class Base(unittest.TestCase):
    def check(self, rng, expectations):
        for version, expected in expectations:
            with self.subTest(range=rng, version=version):
                self.assertIs(satisfies(version, rng), expected)


class TestExactAndVersions(Base):
    def test_exact_version(self):
        self.check("1.2.3", [("1.2.3", True), ("1.2.4", False)])
        self.check("=1.2.3", [("1.2.3", True)])

    def test_v_prefix_and_build_metadata(self):
        self.check(">=1.0.0", [("v1.2.3", True)])
        self.check("1.2.3", [("1.2.3+build.5", True)])
        self.check(">=1.0.0-rc.1 <1.0.0", [("1.0.0-rc.1+build.1", True)])

    def test_invalid_versions(self):
        self.check(">=1.0.0", [("01.2.3", False), ("1.2", False), ("1.2.3-01", False)])

    def test_alphanumeric_prerelease_with_leading_digit_is_valid(self):
        self.check(">=1.2.3-0 <1.2.4", [("1.2.3-0a", True)])

    def test_invalid_ranges(self):
        self.check("not-a-range", [("1.2.3", False)])
        self.check("1.2.3.4", [("1.2.3", False)])


class TestCaret(Base):
    def test_caret_major(self):
        self.check("^1.2.3", [("1.9.9", True), ("2.0.0", False), ("1.2.2", False)])

    def test_caret_zero_major(self):
        self.check("^0.2.3", [("0.2.9", True), ("0.3.0", False)])

    def test_caret_zero_zero(self):
        self.check("^0.0.3", [("0.0.3", True), ("0.0.4", False)])

    def test_caret_partial_zero(self):
        self.check("^0.0", [("0.0.9", True), ("0.1.0", False)])
        self.check("^0.1", [("0.1.9", True), ("0.2.0", False)])

    def test_caret_x(self):
        self.check("^0.x", [("0.9.9", True), ("1.0.0", False)])
        self.check("^0", [("0.5.0", True), ("1.0.0", False)])
        self.check("^1.x", [("1.0.0", True), ("2.0.0", False)])

    def test_caret_patch_x(self):
        self.check("^1.2.x", [("1.9.0", True), ("1.1.9", False)])
        self.check("^0.0.x", [("0.0.7", True), ("0.1.0", False)])

    def test_caret_prerelease_same_tuple_only(self):
        self.check("^1.2.3-beta.2", [
            ("1.2.3-beta.4", True), ("1.2.3-beta.1", False),
            ("1.2.4-beta.2", False), ("1.9.0", True), ("1.2.3", True)])

    def test_caret_zero_zero_prerelease(self):
        self.check("^0.0.3-beta", [("0.0.3-pr.2", True), ("0.0.4", False), ("0.0.3", True)])


class TestTilde(Base):
    def test_tilde_full(self):
        self.check("~1.2.3", [("1.2.9", True), ("1.3.0", False), ("1.2.2", False)])
        self.check("~0.2.3", [("0.2.5", True), ("0.3.0", False)])

    def test_tilde_partial(self):
        self.check("~1.2", [("1.2.0", True), ("1.3.0", False)])
        self.check("~1", [("1.9.9", True), ("2.0.0", False)])
        self.check("~0", [("0.9.0", True), ("1.0.0", False)])

    def test_tilde_prerelease(self):
        self.check("~1.2.3-beta.2", [
            ("1.2.3-beta.10", True), ("1.2.4-beta.3", False), ("1.2.4", True)])


class TestXRanges(Base):
    def test_star_and_empty(self):
        self.check("*", [("1.2.3", True)])
        self.check("", [("0.0.1", True)])
        self.check("x", [("3.0.0", True)])

    def test_star_excludes_prereleases(self):
        self.check("*", [("1.0.0-rc.1", False)])
        self.check("", [("1.0.0-rc.1", False)])

    def test_major_x(self):
        self.check("1.x", [("1.9.9", True), ("2.0.0", False), ("0.9.9", False)])
        self.check("1", [("1.4.0", True), ("2.0.0", False)])

    def test_minor_x(self):
        self.check("1.2.X", [("1.2.7", True)])
        self.check("1.2.*", [("1.3.0", False)])
        self.check("1.2", [("1.2.9", True), ("1.3.0", False)])

    def test_x_range_excludes_prerelease(self):
        self.check("1.2.x", [("1.2.3-beta", False)])


class TestPartialComparators(Base):
    def test_greater_than_partial(self):
        self.check(">1", [("2.0.0", True), ("1.9.9", False)])
        self.check(">1.2", [("1.3.0", True), ("1.2.9", False)])
        self.check(">=1.2", [("1.2.0", True), ("1.1.9", False)])

    def test_less_than_partial(self):
        self.check("<1.2", [("1.1.9", True), ("1.2.0", False)])
        self.check("<=1.2", [("1.2.9", True), ("1.3.0", False)])
        self.check("<=1", [("1.9.9", True), ("2.0.0", False)])


class TestHyphen(Base):
    def test_full_hyphen_inclusive(self):
        self.check("1.2.3 - 2.3.4", [
            ("2.3.4", True), ("2.3.5", False), ("1.2.2", False), ("1.2.3", True)])

    def test_partial_lower(self):
        self.check("1.2 - 2.3.4", [("1.2.0", True), ("1.1.9", False)])

    def test_partial_upper(self):
        self.check("1.2.3 - 2.3", [("2.3.9", True), ("2.4.0", False)])
        self.check("1.2.3 - 2", [("2.9.9", True), ("3.0.0", False)])

    def test_prerelease_lower(self):
        self.check("1.2.3-alpha - 1.2.3", [("1.2.3-beta", True)])


class TestSetsAndUnions(Base):
    def test_intersection(self):
        self.check(">=1.2.7 <1.3.0", [("1.2.8", True), ("1.3.0", False), ("1.2.6", False)])

    def test_union(self):
        self.check("1.2.7 || >=1.2.9 <2.0.0", [
            ("1.2.8", False), ("1.4.6", True), ("1.2.7", True)])

    def test_union_spacing(self):
        self.check("1.x||2.x", [("2.5.0", True), ("3.0.0", False)])
        self.check(" 1.x ||  >=3.0.0 ", [("3.1.0", True)])


class TestPrereleaseRules(Base):
    def test_prerelease_needs_same_tuple_comparator(self):
        self.check(">1.2.3-alpha.3", [
            ("1.2.3-alpha.7", True), ("3.4.5-alpha.9", False), ("3.4.5", True)])

    def test_prerelease_of_upper_bound_excluded(self):
        self.check("<2.0.0", [("2.0.0-beta", False)])
        self.check(">=1.0.0 <2.0.0", [("1.5.0-rc.1", False)])

    def test_prerelease_allowed_in_one_branch_of_union(self):
        self.check("^1.0.0 || >=2.0.0-rc.1 <2.0.0", [("2.0.0-rc.2", True), ("2.0.0-rc.0", False)])

    def test_numeric_identifiers_compare_numerically(self):
        self.check(">=1.0.0-beta.2 <1.0.0", [("1.0.0-beta.11", True), ("1.0.0-alpha.beta", False)])

    def test_numeric_identifier_lower_than_alphanumeric(self):
        self.check(">1.0.0-alpha.1", [("1.0.0-alpha.beta", True)])

    def test_more_identifiers_is_greater(self):
        self.check(">1.0.0-alpha", [("1.0.0-alpha.1", True)])

    def test_prerelease_below_release(self):
        self.check("<1.0.0-rc.1", [("1.0.0-beta", True)])
        self.check(">1.0.0-rc.1", [("1.0.0", True)])
        self.check(">=1.0.0-alpha.1", [("1.0.0-alpha", False)])


class TestMaxSatisfying(unittest.TestCase):
    def test_tilde_and_caret_zero(self):
        self.assertEqual(max_satisfying(["1.2.3", "1.2.4", "1.2.5", "1.2.6", "2.0.1"], "~1.2.3"), "1.2.6")
        self.assertEqual(max_satisfying(["0.1.0", "0.2.0", "0.2.5", "0.3.0"], "^0.2.0"), "0.2.5")

    def test_skips_prereleases(self):
        self.assertEqual(max_satisfying(["1.2.3", "1.2.4-beta", "1.3.0-alpha"], "^1.2.3"), "1.2.3")
        self.assertEqual(max_satisfying(["2.0.0-rc.1", "1.9.9"], "*"), "1.9.9")

    def test_prerelease_ordering(self):
        self.assertEqual(max_satisfying(["1.2.4-beta.2", "1.2.4-beta.10", "1.2.4-beta.9"],
                                        ">=1.2.4-beta.1 <1.2.5"), "1.2.4-beta.10")

    def test_numeric_not_lexical(self):
        self.assertEqual(max_satisfying(["10.0.0", "9.0.0", "2.0.0"], "*"), "10.0.0")
        self.assertEqual(max_satisfying(["1.9.0", "1.10.0", "1.2.0"], "^1.0.0"), "1.10.0")

    def test_invalid_entries_skipped_and_none(self):
        self.assertEqual(max_satisfying(["1.0.0", "garbage", "1.5.0"], "1.x"), "1.5.0")
        self.assertIsNone(max_satisfying(["1.0.0"], "2.x"))
        self.assertIsNone(max_satisfying(["1.0.0"], "not-a-range"))


if __name__ == "__main__":
    unittest.main()
