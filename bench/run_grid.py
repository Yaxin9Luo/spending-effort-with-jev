#!/usr/bin/env python3
"""Run every task at every effort level with headless Claude Code, then grade.

Each run gets a fresh copy of the task workspace outside the repo, so the agent
can't see hidden tests. Grading happens on a second copy with hidden_tests/
added. Results append to bench/results/runs.jsonl; finished runs are skipped,
so the script can be re-run to resume.

  python3 bench/run_grid.py --tasks 'e0*' --levels low,medium --reps 1 -j 4
"""
import argparse
import concurrent.futures as cf
import fnmatch
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
TASKS = BENCH / "tasks"
RESULTS = Path(os.environ.get("EFFORT_RESULTS", BENCH / "results"))
RUN_ROOT = Path(os.environ.get("EFFORT_RUN_ROOT",
                               Path(tempfile.gettempdir()) / "effort-bench-runs"))
MODEL = "claude-opus-5-5"
TIMEOUT_S = 90 * 60
LOCK = threading.Lock()

# Clean environment: no user/project settings, plugins, hooks, MCP servers,
# skills, CLAUDE.md or auto memory.
ENV_OVERRIDES = {
    "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
}
CLAUDE_FLAGS = [
    "--model", MODEL,
    "--output-format", "stream-json", "--verbose",
    "--setting-sources", "",
    "--strict-mcp-config",
    "--disable-slash-commands",
    "--no-session-persistence",
    "--permission-mode", "bypassPermissions",
]


def done_keys():
    f = RESULTS / "runs.jsonl"
    if not f.exists():
        return set()
    keys = set()
    for line in f.read_text().splitlines():
        r = json.loads(line)
        if not r.get("infra_error"):
            keys.add((r["task"], r["level"], r["rep"]))
    return keys


def grade(ws: Path, task_dir: Path):
    g = Path(tempfile.mkdtemp(prefix="grade-"))
    shutil.copytree(ws, g, dirs_exist_ok=True)
    shutil.copytree(task_dir / "hidden_tests", g / "hidden_tests", dirs_exist_ok=True)
    p = subprocess.run(
        ["python3", "-m", "unittest", "discover", "-s", "hidden_tests", "-t", "."],
        cwd=g, capture_output=True, text=True, timeout=600)
    out = p.stderr + p.stdout
    shutil.rmtree(g, ignore_errors=True)
    m = re.search(r"Ran (\d+) test", out)
    ran = int(m.group(1)) if m else 0
    bad = 0
    m = re.search(r"FAILED \(([^)]*)\)", out)
    if m:
        bad = sum(int(n) for n in re.findall(r"=(\d+)", m.group(1)))
    return {"passed": p.returncode == 0 and ran > 0, "tests_run": ran,
            "tests_failed": bad if ran else None, "grader_tail": out[-1500:]}


def run_one(task_dir: Path, level: str, rep: int):
    task = task_dir.name
    prompt = (task_dir / "prompt.txt").read_text()
    run_dir = RUN_ROOT / task / level / f"r{rep}"
    shutil.rmtree(run_dir, ignore_errors=True)
    ws = run_dir / "ws"
    shutil.copytree(task_dir / "workspace", ws)
    env = {**os.environ, **ENV_OVERRIDES}
    env.pop("CLAUDE_EFFORT", None)
    env.pop("CLAUDE_CODE_EFFORT_LEVEL", None)
    t0 = time.time()
    rec = {"task": task, "tier": task[0], "level": level, "rep": rep,
           "model": MODEL, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        p = subprocess.run(["claude", "-p", prompt, "--effort", level, *CLAUDE_FLAGS],
                           cwd=ws, env=env, capture_output=True, text=True,
                           timeout=TIMEOUT_S)
        (run_dir / "transcript.jsonl").write_text(p.stdout)
        (run_dir / "stderr.txt").write_text(p.stderr)
        final = None
        for line in reversed(p.stdout.splitlines()):
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "result":
                final = ev
                break
        if not final or final.get("is_error") and not final.get("total_cost_usd"):
            rec["infra_error"] = (final or {}).get("result") or p.stderr[-500:] or "no result event"
        else:
            u = final.get("usage", {})
            rec.update({
                "cost_usd": final.get("total_cost_usd"),
                "duration_s": round(final.get("duration_ms", 0) / 1000, 1),
                "num_turns": final.get("num_turns"),
                "output_tokens": u.get("output_tokens"),
                "input_tokens": (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                                 + u.get("cache_creation_input_tokens", 0)),
                "agent_error": bool(final.get("is_error")),
                "touched_hidden_tests": "hidden_tests" in p.stdout,
            })
    except subprocess.TimeoutExpired as e:
        (run_dir / "transcript.jsonl").write_text((e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))
        rec.update({"timed_out": True, "duration_s": TIMEOUT_S})
    rec["wall_s"] = round(time.time() - t0, 1)
    if not rec.get("infra_error"):
        rec.update(grade(ws, task_dir))
    with LOCK:
        RESULTS.mkdir(parents=True, exist_ok=True)
        with open(RESULTS / "runs.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
    status = "INFRA" if rec.get("infra_error") else ("PASS" if rec.get("passed") else "fail")
    print(f"{status:5s} {task:28s} {level:6s} r{rep} ${rec.get('cost_usd') or 0:.2f} "
          f"{rec.get('duration_s', 0)}s", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="*")
    ap.add_argument("--levels", default="low,medium,high,xhigh,max")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("-j", "--jobs", type=int, default=4)
    a = ap.parse_args()
    tasks = sorted(d for d in TASKS.iterdir()
                   if d.is_dir() and fnmatch.fnmatch(d.name, a.tasks))
    done = done_keys()
    todo = [(t, lv, r) for r in range(a.reps) for lv in a.levels.split(",")
            for t in tasks if (t.name, lv, r) not in done]
    print(f"{len(todo)} runs to do ({len(done)} already done)", flush=True)
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        list(ex.map(lambda x: run_one(*x), todo))


if __name__ == "__main__":
    main()
