"""Hidden tests for h05_money_split."""
import random
import unittest
from decimal import Decimal as D
from fractions import Fraction

from billing.invoice import Invoice
from billing.money import format_money, from_cents, parse_money, to_cents
from billing.split import split_by_weights, split_evenly


def _frac(x):
    if isinstance(x, float):
        return Fraction(D(repr(x)))
    return Fraction(D(x) if isinstance(x, str) else x)


def oracle(total, weights):
    """Largest-remainder split exactly as the docstring describes."""
    cents_f = _frac(total) * 100
    # half away from zero
    mag = abs(cents_f)
    cents = int(mag) + (1 if mag - int(mag) >= Fraction(1, 2) else 0)
    sign = -1 if cents_f < 0 else 1
    ws = [_frac(w) for w in weights]
    tot = sum(ws)
    exact = [cents * w / tot for w in ws]
    shares = [int(e) for e in exact]
    left = cents - sum(shares)
    order = sorted(range(len(ws)), key=lambda i: (-(exact[i] - shares[i]), i))
    for i in order[:left]:
        shares[i] += 1
    return [D(sign * s) / 100 for s in shares]


def rand_total(rng, allow_negative=True):
    cents = rng.choice([rng.randint(0, 300), rng.randint(0, 10**7)])
    if allow_negative and rng.random() < 0.5:
        cents = -cents
    return f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def rand_weights(rng):
    n = rng.randint(1, 7)
    kind = rng.choice(["int", "float", "decimal"])
    ints = [rng.choice([0, 1, 1, 2, 3, 5, 7, 10]) for _ in range(n)]
    if not any(ints):
        ints[0] = 1
    if kind == "int":
        return ints
    if kind == "float":
        return [i / 10 for i in ints]
    return [D(i) / 4 for i in ints]


class TestToCents(unittest.TestCase):
    def test_floats_use_shortest_repr(self):
        for value, cents in ((0.29, 29), (19.99, 1999), (-0.29, -29), (0.1 + 0.2, 30), (4.35, 435)):
            with self.subTest(value=value):
                self.assertEqual(to_cents(value), cents)

    def test_half_away_from_zero(self):
        for value, cents in ((1.005, 101), (-1.005, -101), ("10.005", 1001), ("-10.005", -1001),
                             (D("0.125"), 13), (2.675, 268), ("0.994", 99), ("-0.994", -99)):
            with self.subTest(value=value):
                self.assertEqual(to_cents(value), cents)

    def test_large_amount_exact(self):
        self.assertEqual(to_cents("12345678901234567.89"), 1234567890123456789)

    def test_plain_values_regression(self):
        self.assertEqual(to_cents("12.34"), 1234)
        self.assertEqual(to_cents(5), 500)
        self.assertEqual(to_cents(D("1.1")), 110)


class TestSplitNegative(unittest.TestCase):
    def test_refund_split_evenly(self):
        shares = split_evenly("-100.00", 3)
        self.assertEqual(shares, [D("-33.34"), D("-33.33"), D("-33.33")])
        self.assertEqual(sum(shares), D("-100.00"))

    def test_refund_by_weights(self):
        self.assertEqual(split_by_weights("-10.00", [1, 2]), [D("-3.33"), D("-6.67")])

    def test_refund_ties_go_to_earlier_party(self):
        self.assertEqual(split_by_weights("-1.00", [1, 1, 1]), [D("-0.34"), D("-0.33"), D("-0.33")])
        self.assertEqual(split_by_weights("-0.02", [1, 1, 1]), [D("-0.01"), D("-0.01"), D("0.00")])

    def test_refund_with_zero_weight(self):
        self.assertEqual(split_by_weights("-1.01", [0, 1, 1]), [D("0.00"), D("-0.51"), D("-0.50")])

    def test_negative_is_mirror_of_positive(self):
        rng = random.Random(11)
        for _ in range(300):
            total = rand_total(rng, allow_negative=False)
            weights = rand_weights(rng)
            with self.subTest(total=total, weights=weights):
                pos = split_by_weights(total, weights)
                neg = split_by_weights("-" + total, weights)
                self.assertEqual(neg, [-s for s in pos])


class TestSplitExactness(unittest.TestCase):
    def test_float_weights_split_like_equivalent_ints(self):
        self.assertEqual(split_by_weights("0.02", [0.3, 0.1]), [D("0.02"), D("0.00")])
        self.assertEqual(split_by_weights("0.03", [0.5, 0.1]), split_by_weights("0.03", [5, 1]))

    def test_float_weights_property(self):
        rng = random.Random(5)
        for _ in range(300):
            ints = [rng.randint(1, 9) for _ in range(rng.randint(2, 5))]
            total = rand_total(rng)
            with self.subTest(total=total, ints=ints):
                self.assertEqual(split_by_weights(total, [i / 10 for i in ints]),
                                 split_by_weights(total, ints))

    def test_float_total(self):
        self.assertEqual(split_evenly(0.29, 1), [D("0.29")])
        self.assertEqual(split_evenly(0.29, 2), [D("0.15"), D("0.14")])

    def test_decimal_weights(self):
        self.assertEqual(split_by_weights("1.00", [D("0.5"), D("0.25"), D("0.25")]),
                         [D("0.50"), D("0.25"), D("0.25")])
        self.assertEqual(split_by_weights("0.01", [D("1"), D("1")]), [D("0.01"), D("0.00")])

    def test_huge_total_adds_up(self):
        shares = split_by_weights("123456789012345678.91", [1, 1, 1])
        self.assertEqual(sum(shares), D("123456789012345678.91"))
        self.assertEqual(shares, [D("41152263004115226.31"), D("41152263004115226.30"),
                                  D("41152263004115226.30")])

    def test_matches_largest_remainder_rule(self):
        rng = random.Random(1234)
        for _ in range(500):
            total = rand_total(rng)
            weights = rand_weights(rng)
            with self.subTest(total=total, weights=weights):
                got = split_by_weights(total, weights)
                self.assertEqual(got, oracle(total, weights))
                self.assertEqual(sum(got), D(total))


class TestSplitRegression(unittest.TestCase):
    def test_even_positive(self):
        self.assertEqual(split_evenly("100.00", 3), [D("33.34"), D("33.33"), D("33.33")])
        self.assertEqual(split_by_weights("0.02", [1, 1, 1]), [D("0.01"), D("0.01"), D("0.00")])

    def test_zero_weights(self):
        self.assertEqual(split_by_weights("1.01", [0, 1, 1]), [D("0.00"), D("0.51"), D("0.50")])

    def test_two_decimal_places(self):
        self.assertEqual([str(s) for s in split_evenly("1", 3)], ["0.34", "0.33", "0.33"])

    def test_validation(self):
        for weights in ([], [0, 0], [0.0, 0.0], [1, -1]):
            with self.subTest(weights=weights):
                with self.assertRaises(ValueError):
                    split_by_weights("1.00", weights)
        for n in (0, -1):
            with self.assertRaises(ValueError):
                split_evenly("1.00", n)


class TestInvoice(unittest.TestCase):
    def test_line_totals_round_half_up(self):
        inv = Invoice().add_line("Coffee", 3, 2.675).add_line("Mug", 1, "9.075")
        self.assertEqual([l.cents for l in inv.lines], [803, 908])

    def test_tax_rounds_half_up(self):
        inv = Invoice(discount_pct=10, tax_pct=8)
        inv.add_line("Widget", 2, "3.50").add_line("Gadget", 1, "12.00")
        self.assertEqual(inv.discount_cents(), 190)
        self.assertEqual(inv.tax_cents(), 137)
        self.assertEqual(inv.total_cents(), 1847)

    def test_discount_rounds_half_up(self):
        inv = Invoice(discount_pct=12.5).add_line("Sticker", 1, "0.20")
        self.assertEqual(inv.discount_cents(), 3)
        self.assertEqual(inv.total_cents(), 17)

    def test_credit_line(self):
        inv = Invoice().add_line("Credit", 1, "-5.005").add_line("Item", 1, "10.00")
        self.assertEqual(inv.lines[0].cents, -501)
        self.assertEqual(inv.total_cents(), 499)

    def test_split_credit_note(self):
        inv = Invoice().add_line("Refund", 1, "-100.00")
        self.assertEqual(inv.split([1, 1, 1]), [D("-33.34"), D("-33.33"), D("-33.33")])

    def test_existing_totals_regression(self):
        inv = Invoice(discount_pct=10, tax_pct=10)
        inv.add_line("Widget", 2, "3.50").add_line("Gadget", 1, "12.00")
        self.assertEqual((inv.subtotal_cents(), inv.discount_cents(), inv.tax_cents(),
                          inv.total_cents()), (1900, 190, 171, 1881))
        self.assertIn("$18.81", inv.render())


class TestFormatting(unittest.TestCase):
    def test_format_and_parse_regression(self):
        self.assertEqual(format_money(123456), "$1,234.56")
        self.assertEqual(format_money(-5), "-$0.05")
        self.assertEqual(format_money(0), "$0.00")
        self.assertEqual(parse_money("$1,234.56"), 123456)
        self.assertEqual(parse_money("(3.50)"), -350)
        self.assertEqual(parse_money("-$0.05"), -5)
        self.assertEqual(from_cents(-5), D("-0.05"))


if __name__ == "__main__":
    unittest.main()
