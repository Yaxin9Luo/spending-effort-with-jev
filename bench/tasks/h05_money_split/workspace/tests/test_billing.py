import unittest
from decimal import Decimal as D

from billing.invoice import Invoice
from billing.money import format_money, from_cents, parse_money, to_cents
from billing.split import split_by_weights, split_evenly


class TestMoney(unittest.TestCase):
    def test_to_cents(self):
        self.assertEqual(to_cents("12.34"), 1234)
        self.assertEqual(to_cents(5), 500)
        self.assertEqual(to_cents(D("0.50")), 50)

    def test_from_cents(self):
        self.assertEqual(from_cents(1234), D("12.34"))
        self.assertEqual(str(from_cents(5)), "0.05")

    def test_format(self):
        self.assertEqual(format_money(123456), "$1,234.56")
        self.assertEqual(format_money(-5), "-$0.05")

    def test_parse(self):
        self.assertEqual(parse_money("$1,234.56"), 123456)
        self.assertEqual(parse_money("(3.50)"), -350)


class TestSplit(unittest.TestCase):
    def test_even(self):
        self.assertEqual(split_evenly("100.00", 3), [D("33.34"), D("33.33"), D("33.33")])

    def test_weights(self):
        self.assertEqual(split_by_weights("10.00", [1, 2, 2]), [D("2.00"), D("4.00"), D("4.00")])

    def test_zero_weight(self):
        self.assertEqual(split_by_weights("5.00", [0, 1]), [D("0.00"), D("5.00")])

    def test_bad_weights(self):
        for w in ([], [0, 0], [1, -1]):
            with self.assertRaises(ValueError):
                split_by_weights("1.00", w)


class TestInvoice(unittest.TestCase):
    def test_totals(self):
        inv = Invoice(discount_pct=10, tax_pct=10)
        inv.add_line("Widget", 2, "3.50").add_line("Gadget", 1, "12.00")
        self.assertEqual(inv.subtotal_cents(), 1900)
        self.assertEqual(inv.discount_cents(), 190)
        self.assertEqual(inv.tax_cents(), 171)
        self.assertEqual(inv.total_cents(), 1881)

    def test_split(self):
        inv = Invoice().add_line("Dinner", 1, "90.00")
        self.assertEqual(inv.split([1, 1]), [D("45.00"), D("45.00")])


if __name__ == "__main__":
    unittest.main()
