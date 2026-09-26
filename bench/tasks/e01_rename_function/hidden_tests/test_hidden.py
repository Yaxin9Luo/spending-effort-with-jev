import ast
import os
import re
import subprocess
import sys
import unittest


def py_files():
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ("hidden_tests", "__pycache__", ".git")]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


def identifiers(path):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.Attribute):
            yield node.attr
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name
        elif isinstance(node, ast.alias):
            yield node.name
            if node.asname:
                yield node.asname


class RenameTest(unittest.TestCase):
    def test_new_name_same_behaviour(self):
        from shop.pricing import compute_order_total
        self.assertEqual(compute_order_total([(10.0, 2), (5.0, 1)]), 27.0)
        self.assertEqual(compute_order_total([(100.0, 1)], discount=0.25), 81.0)
        self.assertEqual(compute_order_total([]), 0.0)

    def test_old_name_gone_from_module(self):
        import shop.pricing
        self.assertFalse(hasattr(shop.pricing, "calc_total"))

    def test_old_name_not_used_anywhere(self):
        offenders = [p for p in py_files() if "calc_total" in set(identifiers(p))]
        self.assertEqual(offenders, [])

    def test_checkout_call_site(self):
        from shop.checkout import checkout
        self.assertEqual(checkout([(50.0, 2)], coupon="SAVE10"), {"items": 2, "total": 97.2})
        self.assertEqual(checkout([(20.0, 1)], coupon="BOGUS"), {"items": 1, "total": 21.6})

    def test_reports_call_site(self):
        from shop.reports import daily_summary
        s = daily_summary([[(10.0, 2), (5.0, 1)], [(100.0, 1)]])
        self.assertEqual(s, {"orders": 2, "revenue": 135.0, "largest": 108.0})

    def test_existing_suite_passes(self):
        p = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        m = re.search(r"Ran (\d+) test", p.stderr)
        self.assertTrue(m and int(m.group(1)) >= 3, p.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
