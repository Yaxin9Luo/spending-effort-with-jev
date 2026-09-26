import os
import subprocess
import sys
import tempfile
import unittest

TEXT = "The cat and the hat sat on the mat. A big elephant ate apples and apples.\n"


def run_cli(*args):
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(TEXT)
    try:
        p = subprocess.run([sys.executable, "-m", "wc_tool.cli", path, *args],
                           capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    return p


def parse(out):
    result = {}
    for line in out.strip().splitlines():
        n, word = line.split("\t")
        result[word] = int(n)
    return result


class CountWordsTest(unittest.TestCase):
    def test_default_unchanged(self):
        from wc_tool.counter import count_words
        c = count_words("a bb ccc bb A")
        self.assertEqual(dict(c), {"a": 2, "bb": 2, "ccc": 1})

    def test_min_length_keyword(self):
        from wc_tool.counter import count_words
        self.assertEqual(dict(count_words("a bb ccc bb A", min_length=2)), {"bb": 2, "ccc": 1})
        self.assertEqual(dict(count_words("a bb ccc bb A", min_length=3)), {"ccc": 1})
        self.assertEqual(dict(count_words("a bb ccc", min_length=1)), {"a": 1, "bb": 1, "ccc": 1})


class CliTest(unittest.TestCase):
    def test_no_flag_same_as_before(self):
        p = run_cli("--top", "50")
        self.assertEqual(p.returncode, 0, p.stderr)
        got = parse(p.stdout)
        self.assertEqual(got["the"], 3)
        self.assertEqual(got["a"], 1)
        self.assertEqual(got["on"], 1)

    def test_min_length_flag(self):
        p = run_cli("--top", "50", "--min-length", "4")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(parse(p.stdout), {"apples": 2, "elephant": 1})

    def test_min_length_with_top(self):
        p = run_cli("--min-length", "3", "--top", "1")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(parse(p.stdout), {"the": 3})

    def test_help_mentions_flag(self):
        p = subprocess.run([sys.executable, "-m", "wc_tool.cli", "--help"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0)
        self.assertIn("--min-length", p.stdout)


if __name__ == "__main__":
    unittest.main()
