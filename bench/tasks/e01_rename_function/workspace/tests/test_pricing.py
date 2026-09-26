import unittest

from shop.checkout import checkout
from shop.pricing import calc_total


class PricingTest(unittest.TestCase):
    def test_total_with_tax(self):
        self.assertEqual(calc_total([(10.0, 2), (5.0, 1)]), 27.0)

    def test_discount(self):
        self.assertEqual(calc_total([(100.0, 1)], discount=0.25), 81.0)

    def test_checkout_coupon(self):
        self.assertEqual(checkout([(50.0, 2)], coupon="SAVE10"), {"items": 2, "total": 97.2})


if __name__ == "__main__":
    unittest.main()
