import subprocess
import sys
import unittest


class TotalsTest(unittest.TestCase):
    def test_line_without_discount(self):
        from invoicing.totals import line_total
        self.assertEqual(line_total({"sku": "X", "unit_price": 12.0, "quantity": 2}), 24.0)

    def test_line_with_discount_unchanged(self):
        from invoicing.totals import line_total
        self.assertEqual(line_total({"unit_price": 2.5, "quantity": 10, "discount": 0.1}), 22.5)
        self.assertEqual(line_total({"unit_price": 4.0, "quantity": 3, "discount": 0.0}), 12.0)

    def test_invoice_total_mixed(self):
        from invoicing.totals import invoice_total
        inv = {"id": "T", "lines": [
            {"unit_price": 12.0, "quantity": 2},
            {"unit_price": 2.5, "quantity": 4, "discount": 0.2},
            {"unit_price": 7.25, "quantity": 1},
        ]}
        self.assertEqual(invoice_total(inv), 39.25)

    def test_invoice_savings_mixed(self):
        from invoicing.totals import invoice_savings
        inv = {"id": "T", "lines": [
            {"unit_price": 12.0, "quantity": 2},
            {"unit_price": 2.5, "quantity": 4, "discount": 0.2},
        ]}
        self.assertEqual(invoice_savings(inv), 2.0)
        self.assertEqual(invoice_savings({"id": "U", "lines": [{"unit_price": 1.0, "quantity": 1}]}), 0.0)

    def test_cli_on_sample_invoices(self):
        p = subprocess.run(
            [sys.executable, "-m", "invoicing.cli", "invoices/INV-1001.json", "invoices/INV-1002.json"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        self.assertEqual(p.stdout.splitlines(), [
            "INV-1001: total 34.50, saved 2.50",
            "INV-1002: total 39.25, saved 2.00",
        ])


if __name__ == "__main__":
    unittest.main()
