import ast
import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

LOGGER = "backup.sync"


class SyncLoggingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "src")
        self.dst = os.path.join(self.tmp, "dst")
        os.makedirs(os.path.join(self.src, "nested"))
        for name in ("a.txt", "b.txt"):
            with open(os.path.join(self.src, name), "w") as f:
                f.write(name)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_sync(self, src, dst):
        from backup.sync import sync_dir
        buf = io.StringIO()
        with self.assertLogs(LOGGER, level="DEBUG") as cm, redirect_stdout(buf):
            n = sync_dir(src, dst)
        self.assertEqual(buf.getvalue(), "", "sync_dir should not print anything")
        return n, [(r.levelno, r.getMessage()) for r in cm.records]

    def find(self, records, needle):
        return [(lvl, msg) for lvl, msg in records if needle in msg]

    def test_module_logger(self):
        import backup.sync as mod
        self.assertIsInstance(getattr(mod, "logger", None), logging.Logger)
        self.assertEqual(mod.logger.name, LOGGER)

    def test_first_run_levels(self):
        n, recs = self.run_sync(self.src, self.dst)
        self.assertEqual(n, 2)
        self.assertTrue(os.path.exists(os.path.join(self.dst, "a.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dst, "b.txt")))
        copied_a = self.find(recs, "a.txt")
        self.assertEqual(len(copied_a), 1)
        self.assertEqual(copied_a[0][0], logging.INFO)
        self.assertIn("copied", copied_a[0][1])
        skip = self.find(recs, "nested")
        self.assertEqual(len(skip), 1)
        self.assertEqual(skip[0][0], logging.WARNING)
        self.assertFalse(skip[0][1].startswith("WARNING"))
        self.assertIn("skipping subdirectory", skip[0][1])
        done = self.find(recs, "done")
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0][0], logging.INFO)
        self.assertIn("2", done[0][1])

    def test_second_run_up_to_date_is_debug(self):
        self.run_sync(self.src, self.dst)
        n, recs = self.run_sync(self.src, self.dst)
        self.assertEqual(n, 0)
        up = self.find(recs, "up to date")
        self.assertEqual(len(up), 2)
        self.assertTrue(all(lvl == logging.DEBUG for lvl, _ in up))
        done = self.find(recs, "done")
        self.assertEqual(done[0][0], logging.INFO)
        self.assertIn("0", done[0][1])

    def test_missing_source_is_error(self):
        missing = os.path.join(self.tmp, "nope")
        n, recs = self.run_sync(missing, self.dst)
        self.assertEqual(n, 0)
        err = self.find(recs, missing)
        self.assertEqual(len(err), 1)
        self.assertEqual(err[0][0], logging.ERROR)
        self.assertFalse(err[0][1].startswith("ERROR"))
        self.assertIn("source directory not found", err[0][1])

    def test_no_print_calls_left(self):
        with open(os.path.join("backup", "sync.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        prints = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"]
        self.assertEqual(prints, [])

    def test_import_does_not_configure_root_logging(self):
        code = "import logging, backup.sync; print(len(logging.getLogger().handlers))"
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "0")


if __name__ == "__main__":
    unittest.main()
