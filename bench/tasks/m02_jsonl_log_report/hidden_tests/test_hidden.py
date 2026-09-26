import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "logreport.py")


def rec(path, status, ms, **extra):
    d = {"path": path, "status": status, "ms": ms}
    d.update(extra)
    return json.dumps(d)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, lines):
        p = os.path.join(self.tmp.name, "log.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return p

    def run_cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, SCRIPT, *args], input=stdin,
                              capture_output=True, text=True, timeout=60, cwd=ROOT)

    def report(self, *args, stdin=None):
        p = self.run_cli(*args, stdin=stdin)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def group(self, rep, key):
        for g in rep["groups"]:
            if g["key"] == key:
                return g
        self.fail(f"no group {key!r} in {rep['groups']}")


class TestAggregation(Base):
    def test_basic_by_path(self):
        p = self.write([
            rec("/a", 200, 10), rec("/a", 500, 20), rec("/a", 503, 33),
            rec("/b", 200, 1.5),
        ])
        rep = self.report(p)
        self.assertEqual(rep["total"], 4)
        self.assertEqual(rep["skipped"], 0)
        self.assertEqual([g["key"] for g in rep["groups"]], ["/a", "/b"])
        a = self.group(rep, "/a")
        self.assertEqual(a["count"], 3)
        self.assertEqual(a["errors"], 2)
        self.assertAlmostEqual(a["avg_ms"], 21.0)
        self.assertEqual(a["p95_ms"], 33)
        b = self.group(rep, "/b")
        self.assertEqual(b["errors"], 0)
        self.assertAlmostEqual(b["avg_ms"], 1.5)
        self.assertAlmostEqual(b["p95_ms"], 1.5)

    def test_error_threshold_is_500(self):
        p = self.write([rec("/x", 499, 1), rec("/x", 500, 1), rec("/x", 404, 1)])
        self.assertEqual(self.group(self.report(p), "/x")["errors"], 1)

    def test_avg_rounding(self):
        p = self.write([rec("/r", 200, 1), rec("/r", 200, 1), rec("/r", 200, 2)])
        self.assertAlmostEqual(self.group(self.report(p), "/r")["avg_ms"], 1.33, places=6)

    def test_p95_nearest_rank(self):
        # 20 values 1..20 -> rank ceil(19.0)=19 -> 19
        lines = [rec("/p", 200, v) for v in reversed(range(1, 21))]
        # 21 values -> rank ceil(19.95)=20 -> value 20
        lines += [rec("/q", 200, v) for v in range(1, 22)]
        rep = self.report(self.write(lines))
        self.assertEqual(self.group(rep, "/p")["p95_ms"], 19)
        self.assertEqual(self.group(rep, "/q")["p95_ms"], 20)

    def test_p95_small_group(self):
        rep = self.report(self.write([rec("/s", 200, 7), rec("/s", 200, 3)]))
        self.assertEqual(self.group(rep, "/s")["p95_ms"], 7)

    def test_sort_count_desc_then_key_asc(self):
        lines = [rec("/z", 200, 1)] * 2 + [rec("/b", 200, 1)] * 2 + [rec("/m", 200, 1)] * 3 + [rec("/a", 200, 1)]
        rep = self.report(self.write(lines))
        self.assertEqual([g["key"] for g in rep["groups"]], ["/m", "/b", "/z", "/a"])

    def test_top(self):
        lines = [rec("/z", 200, 1)] * 2 + [rec("/b", 200, 1)] * 2 + [rec("/m", 200, 1)] * 3 + [rec("/a", 200, 1)]
        rep = self.report(self.write(lines + ["garbage"]), "--top", "2")
        self.assertEqual([g["key"] for g in rep["groups"]], ["/m", "/b"])
        self.assertEqual(rep["total"], 8)
        self.assertEqual(rep["skipped"], 1)

    def test_by_status(self):
        p = self.write([rec("/a", 200, 1), rec("/b", 200, 3), rec("/a", 503, 9), rec("/c", 404, 2)])
        rep = self.report(p, "--by", "status")
        keys = [g["key"] for g in rep["groups"]]
        self.assertEqual(keys, [200, 404, 503])
        self.assertTrue(all(isinstance(k, int) for k in keys))
        self.assertEqual(self.group(rep, 503)["errors"], 1)
        self.assertEqual(self.group(rep, 200)["count"], 2)
        self.assertAlmostEqual(self.group(rep, 200)["avg_ms"], 2.0)

    def test_extra_fields_ignored(self):
        rep = self.report(self.write([rec("/a", 200, 5, ts="t", user="u")]))
        self.assertEqual(rep["total"], 1)


class TestInputHandling(Base):
    def test_skipped_lines(self):
        lines = [
            rec("/ok", 200, 1),
            "not json",
            "[1, 2, 3]",
            '"just a string"',
            json.dumps({"path": "/a", "status": 200}),
            json.dumps({"path": "/a", "ms": 3}),
            json.dumps({"status": 200, "ms": 3}),
            json.dumps({"path": "/a", "status": "200", "ms": 3}),
            json.dumps({"path": "/a", "status": 200, "ms": "3"}),
            json.dumps({"path": "/a", "status": 200, "ms": True}),
            json.dumps({"path": 5, "status": 200, "ms": 3}),
            json.dumps({"path": "/a", "status": 200, "ms": None}),
            '{"path": "/a", "status": 200, "ms": 3',
        ]
        rep = self.report(self.write(lines))
        self.assertEqual(rep["total"], 1)
        self.assertEqual(rep["skipped"], 12)
        self.assertEqual([g["key"] for g in rep["groups"]], ["/ok"])

    def test_blank_lines_ignored(self):
        rep = self.report(self.write(["", rec("/a", 200, 1), "   ", "\t", rec("/a", 200, 2), ""]))
        self.assertEqual(rep["total"], 2)
        self.assertEqual(rep["skipped"], 0)

    def test_empty_file(self):
        p = os.path.join(self.tmp.name, "empty.jsonl")
        open(p, "w").close()
        rep = self.report(p)
        self.assertEqual(rep, {"total": 0, "skipped": 0, "groups": []})

    def test_stdin(self):
        data = "\n".join([rec("/a", 200, 4), "bad", rec("/a", 500, 6)]) + "\n"
        rep = self.report("-", stdin=data)
        self.assertEqual(rep["total"], 2)
        self.assertEqual(rep["skipped"], 1)
        self.assertEqual(self.group(rep, "/a")["errors"], 1)

    def test_missing_file(self):
        p = self.run_cli(os.path.join(self.tmp.name, "nope.jsonl"))
        self.assertEqual(p.returncode, 2)
        self.assertTrue(p.stderr.strip())

    def test_sample_file(self):
        rep = self.report(os.path.join(ROOT, "sample.jsonl"))
        self.assertEqual(rep["total"], 6)
        self.assertEqual(rep["skipped"], 1)
        users = self.group(rep, "/api/users")
        self.assertEqual(users["count"], 3)
        self.assertAlmostEqual(users["avg_ms"], 15.83)
        self.assertEqual(users["p95_ms"], 30)
        self.assertEqual(rep["groups"][0]["key"], "/api/users")


if __name__ == "__main__":
    unittest.main()
