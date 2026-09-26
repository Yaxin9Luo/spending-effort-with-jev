#!/usr/bin/env python3
"""Check that every task in a tier is well formed and discriminating.

For each bench/tasks/<prefix>* directory:
  - workspace/ + hidden_tests/  must FAIL (so the task isn't already solved)
  - reference/ + hidden_tests/  must PASS (so the task is solvable as graded)
Grading mirrors run_grid.grade(): copy into a temp dir, then run
`python3 -m unittest discover -s hidden_tests -t .` from its root.

  python3 bench/validate_tier.py e0        # easy tier
  python3 bench/validate_tier.py m0 -v     # show grader output on problems
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TASKS = Path(__file__).resolve().parent / "tasks"
REQUIRED = ["prompt.txt", "meta.json", "workspace", "reference", "hidden_tests/test_hidden.py"]


def run_hidden(src: Path, task_dir: Path):
    g = Path(tempfile.mkdtemp(prefix="validate-"))
    try:
        shutil.copytree(src, g, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(task_dir / "hidden_tests", g / "hidden_tests", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        p = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", "hidden_tests", "-t", "."],
            cwd=g, capture_output=True, text=True, timeout=600)
    finally:
        shutil.rmtree(g, ignore_errors=True)
    out = p.stderr + p.stdout
    m = re.search(r"Ran (\d+) test", out)
    ran = int(m.group(1)) if m else 0
    return p.returncode == 0 and ran > 0, ran, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix", help="task-name prefix, e.g. e0")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    tasks = sorted(d for d in TASKS.iterdir() if d.is_dir() and d.name.startswith(a.prefix))
    if not tasks:
        sys.exit(f"no tasks matching {a.prefix!r} in {TASKS}")
    ok_all = True
    print(f"{'task':32s} {'workspace':12s} {'reference':12s}")
    for t in tasks:
        missing = [r for r in REQUIRED if not (t / r).exists()]
        if missing:
            print(f"{t.name:32s} MISSING {missing}")
            ok_all = False
            continue
        meta = json.loads((t / "meta.json").read_text())
        if meta.get("id") != t.name:
            print(f"{t.name:32s} meta.json id mismatch: {meta.get('id')!r}")
            ok_all = False
        ws_pass, ws_ran, ws_out = run_hidden(t / "workspace", t)
        ref_pass, ref_ran, ref_out = run_hidden(t / "reference", t)
        ws_ok, ref_ok = not ws_pass, ref_pass
        ok_all &= ws_ok and ref_ok
        ws_s = f"{'fails' if ws_ok else 'PASSES!'} ({ws_ran})"
        ref_s = f"{'passes' if ref_ok else 'FAILS!'} ({ref_ran})"
        print(f"{t.name:32s} {ws_s:12s} {ref_s:12s}")
        if a.verbose or not ref_ok:
            print("  --- reference output ---\n  " + ref_out[-3000:].replace("\n", "\n  "))
        if a.verbose or not ws_ok:
            print("  --- workspace output ---\n  " + ws_out[-3000:].replace("\n", "\n  "))
    print("ALL OK" if ok_all else "PROBLEMS FOUND")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
