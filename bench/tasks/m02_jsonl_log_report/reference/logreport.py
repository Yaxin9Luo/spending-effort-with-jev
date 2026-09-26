#!/usr/bin/env python3
"""Summarise a JSONL access log."""
import argparse
import json
import math
import sys


def _valid(rec):
    if not isinstance(rec, dict):
        return False
    path, status, ms = rec.get("path"), rec.get("status"), rec.get("ms")
    if not isinstance(path, str):
        return False
    if isinstance(status, bool) or not isinstance(status, int):
        return False
    if isinstance(ms, bool) or not isinstance(ms, (int, float)):
        return False
    return True


def summarise(lines, by="path", top=None):
    total = skipped = 0
    groups = {}
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if not _valid(rec):
            skipped += 1
            continue
        total += 1
        g = groups.setdefault(rec[by], {"count": 0, "errors": 0, "ms": []})
        g["count"] += 1
        if rec["status"] >= 500:
            g["errors"] += 1
        g["ms"].append(rec["ms"])
    out = []
    for key, g in groups.items():
        vals = sorted(g["ms"])
        n = len(vals)
        out.append({
            "key": key,
            "count": g["count"],
            "errors": g["errors"],
            "avg_ms": round(sum(vals) / n, 2),
            "p95_ms": vals[math.ceil(0.95 * n) - 1],
        })
    out.sort(key=lambda d: (-d["count"], d["key"]))
    if top is not None:
        out = out[:top]
    return {"total": total, "skipped": skipped, "groups": out}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("logfile")
    ap.add_argument("--by", choices=["path", "status"], default="path")
    ap.add_argument("--top", type=int, default=None)
    a = ap.parse_args(argv)
    if a.logfile == "-":
        report = summarise(sys.stdin, a.by, a.top)
    else:
        try:
            f = open(a.logfile, encoding="utf-8")
        except OSError as e:
            print(f"logreport: cannot open {a.logfile}: {e}", file=sys.stderr)
            return 2
        with f:
            report = summarise(f, a.by, a.top)
    json.dump(report, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
