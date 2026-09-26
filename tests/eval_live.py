"""Live check against the TypeSafe API. Needs TYPESAFE_API_KEY.
Run: python3 tests/eval_live.py"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "plugins" / "spending-effort-with-jev" / "scripts"))
import effort_advisor as ea  # noqa: E402
# Dev scripts: pass the developer's key to the plugin the way Claude Code would.
import os  # noqa: E402
os.environ.setdefault("CLAUDE_PLUGIN_OPTION_TYPESAFE_API_KEY", os.environ.get("TYPESAFE_API_KEY", ""))

CTX = [{"role": "user", "text": "Add retry logic to the harness: retry failed tool calls 3 times"},
       {"role": "assistant", "text": "Done: added retries in runner.py call_tool."}]

# (prompt, context, acceptable effort choices, expect ambiguity warning)
CASES = [
    ("Why does PPO's clipping approximate a trust region?", [], {"low"}, False),
    ("解释一下 flow matching 和 diffusion 的区别", [], {"low"}, False),
    ("Move all the PDFs on my Desktop into a papers folder", [], {"low"}, False),
    ("Add a --seed flag to the eval script", [], {"low", "medium"}, False),
    ("Write a script that reads jsonl trajectories and counts tokens per step", [], {"medium"}, False),
    ("Training loss goes NaN at step 3000, find the cause and fix it", [], {"high"}, False),
    ("这组 ablation 结果和 baseline 差不多，帮我分析到底有没有显著差异", [], {"high"}, False),
    ("Now test that retry logic properly, including the edge cases", CTX, {"high"}, False),
    ("Tonight, run the whole thing yourself: reproduce every number in table 2 of the paper and write a report", [], {"max"}, None),
    ("Just finish this whole project yourself overnight", [], {"max", "unclear"}, True),
    ("continue", CTX, {"unclear"}, False),
    ("ok", [], {"unclear"}, False),
    ("跑一下", CTX, {"unclear"}, False),
    ("Audit this RL training framework for every possible reward leak, don't ask me", [], {"high", "max"}, None),
]


def main():
    key = ea.api_key()
    if not key:
        sys.exit("Set TYPESAFE_API_KEY first.")
    hits, times = 0, []
    for prompt, ctx, ok, amb_expected in CASES:
        t = time.time()
        a = ea.ask_jev(key, prompt, ctx)
        times.append(time.time() - t)
        choice, conf = a["effort"]["choice"], a["effort"]["confidence"]
        amb = a["handoff_ambiguous"]["noul"] >= ea.AMBIGUITY_MIN
        good = choice in ok and (amb_expected is None or amb == amb_expected)
        hits += good
        print(f"{'ok ' if good else 'MISS'} {choice:8s} conf={conf:.2f} ambiguous={amb!s:5s} | {prompt[:60]}")
    times.sort()
    print(f"\n{hits}/{len(CASES)} as expected; latency median {times[len(times)//2]:.2f}s, max {times[-1]:.2f}s")


if __name__ == "__main__":
    main()
