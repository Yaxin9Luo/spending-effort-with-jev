import importlib
import re
import sys
import tomllib
import unittest


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class VersionBumpTest(unittest.TestCase):
    def test_pyproject(self):
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        self.assertEqual(data["project"]["version"], "1.5.0")
        self.assertEqual(data["project"]["name"], "tinyq")

    def test_package_version(self):
        sys.modules.pop("tinyq", None)
        tinyq = importlib.import_module("tinyq")
        self.assertEqual(tinyq.__version__, "1.5.0")
        self.assertEqual(tuple(tinyq.__version_info__), (1, 5, 0))

    def test_docs_conf(self):
        ns = {}
        exec(compile(read("docs/conf.py"), "docs/conf.py", "exec"), ns)
        self.assertEqual(ns["release"], "1.5.0")
        self.assertEqual(ns["version"], "1.5")
        self.assertEqual(ns["project"], "tinyq")

    def test_no_stale_version_in_versioned_files(self):
        for path in ("pyproject.toml", "tinyq/__init__.py", "docs/conf.py"):
            text = read(path)
            self.assertNotIn("1.4.2", text, path)
            self.assertNotRegex(text, r"\(\s*1\s*,\s*4\s*,\s*2\s*\)", path)

    def test_changelog_release_section(self):
        lines = read("CHANGELOG.md").splitlines()
        heads = [i for i, l in enumerate(lines) if re.match(r"^##\s+\[1\.5\.0\]\s+-\s+2026-09-26\s*$", l)]
        self.assertEqual(len(heads), 1, "expected exactly one '## [1.5.0] - 2026-09-26' heading")
        old = lines.index("## [1.4.2] - 2026-05-02")
        self.assertLess(heads[0], old)
        section = lines[heads[0] + 1:old]
        self.assertIn("- Add `JobQueue.drain()` to run all pending jobs.", section)
        self.assertIn("- `JobQueue` now supports `len()`.", section)
        # the released items should not still be listed under an Unreleased heading
        for i, l in enumerate(lines):
            if "unreleased" in l.lower() and l.startswith("#"):
                nxt = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
                self.assertNotIn("- Add `JobQueue.drain()` to run all pending jobs.", lines[i + 1:nxt])

    def test_changelog_old_entries_untouched(self):
        text = read("CHANGELOG.md")
        tail = ("## [1.4.2] - 2026-05-02\n- Fix `run_next()` losing keyword arguments.\n\n"
                "## [1.4.1] - 2026-03-18\n- Packaging fixes.\n\n"
                "## [1.4.0] - 2026-02-01\n- First public release.\n")
        self.assertIn(tail.rstrip(), text.rstrip())
        self.assertTrue(text.rstrip().endswith(tail.rstrip()))

    def test_queue_still_works(self):
        from tinyq import JobQueue
        q = JobQueue()
        q.submit(lambda x, y=0: x + y, 1, y=2)
        q.submit(str.upper, "a")
        self.assertEqual(len(q), 2)
        self.assertEqual(q.drain(), [3, "A"])


if __name__ == "__main__":
    unittest.main()
