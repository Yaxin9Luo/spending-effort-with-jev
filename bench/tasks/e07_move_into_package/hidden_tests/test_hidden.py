import os
import re
import subprocess
import sys
import tempfile
import unittest

EXPECTED_ALL = (
    "name   team       score\n"
    "-----  ---------  -----\n"
    "Ada    core       91\n"
    "Linus  kernel     78\n"
    "Grace  compilers  88\n"
)
EXPECTED_COLS = "name   score\n-----  -----\nAda    91\nLinus  78\nGrace  88\n"


class MoveTest(unittest.TestCase):
    def test_package_modules(self):
        from tablekit.loader import load_records
        from tablekit.render import render_table
        rows = load_records(os.path.join("data", "sample.csv"))
        self.assertEqual(rows[0], {"name": "Ada", "team": "core", "score": "91"})
        self.assertEqual(render_table([{"a": "x", "b": "long"}], ["a", "b"]), "a  b\n-  ----\nx  long")

    def test_old_modules_removed(self):
        self.assertFalse(os.path.exists("loader.py"))
        self.assertFalse(os.path.exists("render.py"))
        self.assertTrue(os.path.exists("main.py"))

    def run_main(self, *args, cwd=None):
        main = os.path.abspath("main.py")
        return subprocess.run([sys.executable, main, *args], capture_output=True, text=True,
                              timeout=60, cwd=cwd)

    def test_main_output_unchanged(self):
        p = self.run_main("data/sample.csv")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, EXPECTED_ALL)
        p = self.run_main("data/sample.csv", "name", "score")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, EXPECTED_COLS)

    def test_main_from_other_cwd(self):
        sample = os.path.abspath(os.path.join("data", "sample.csv"))
        with tempfile.TemporaryDirectory() as d:
            p = self.run_main(sample, "name", "score", cwd=d)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, EXPECTED_COLS)

    def test_existing_suite_passes(self):
        p = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        m = re.search(r"Ran (\d+) test", p.stderr)
        self.assertTrue(m and int(m.group(1)) >= 2, p.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
