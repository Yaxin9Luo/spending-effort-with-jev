#!/usr/bin/env python3
"""Evaluate the 'ambiguous hand-off' tip on prompts.jsonl + handoff_prompts.jsonl.

Protocol: gold = majority of 3 raters; stratified 50/50 dev/test split on gold
(seed 0); AMBIGUITY_MIN chosen on dev maximising F0.5; test scored once.
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))
import effort_advisor as ea  # noqa: E402
# Dev scripts: pass the developer's key to the plugin the way Claude Code would.
import os  # noqa: E402
os.environ.setdefault("CLAUDE_PLUGIN_OPTION_TYPESAFE_API_KEY", os.environ.get("TYPESAFE_API_KEY", ""))
from analyze import fleiss_kappa, load  # noqa: E402


def jev_cached(prompts, cache_name):
    f = HERE / cache_name
    cache = {r["id"]: r["answers"] for r in load(cache_name)} if f.exists() else {}
    with open(f, "a") as out:
        for p in prompts:
            if p["id"] not in cache:
                a = ea.ask_jev(ea.api_key(), p["prompt"], p["context"])
                cache[p["id"]] = a
                out.write(json.dumps({"id": p["id"], "answers": a}, ensure_ascii=False) + "\n")
    return cache


def gold_amb(prompts, label_fmt):
    raters = [{r["id"]: r for r in load(label_fmt.format(i))} for i in (1, 2, 3)]
    rows, gold = [], {}
    for p in prompts:
        v = [bool(r[p["id"]]["handoff_ambiguous"]) for r in raters]
        rows.append(v)
        gold[p["id"]] = sum(v) >= 2
    return gold, fleiss_kappa(rows, [True, False]), sum(len(set(r)) == 1 for r in rows)


def prf(ids, gold, jev, t):
    tp = sum(jev[i]["handoff_ambiguous"]["noul"] >= t and gold[i] for i in ids)
    fp = sum(jev[i]["handoff_ambiguous"]["noul"] >= t and not gold[i] for i in ids)
    fn = sum(jev[i]["handoff_ambiguous"]["noul"] < t and gold[i] for i in ids)
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 1.25 * p * r / (0.25 * p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3), "f05": round(f, 3)}


def main():
    main_p, hand_p = load("prompts.jsonl"), load("handoff_prompts.jsonl")
    jev = {**jev_cached(main_p, "jev_outputs.jsonl"), **jev_cached(hand_p, "jev_outputs_handoff.jsonl")}
    g1, k1, u1 = gold_amb(main_p, "labels_r{}.jsonl")
    g2, k2, u2 = gold_amb(hand_p, "handoff_labels_r{}.jsonl")
    gold = {**g1, **g2}
    ids = sorted(gold)
    pos = [i for i in ids if gold[i]]
    neg = [i for i in ids if not gold[i]]
    rng = random.Random(0)
    rng.shuffle(pos)
    rng.shuffle(neg)
    dev = pos[: len(pos) // 2] + neg[: len(neg) // 2]
    test = pos[len(pos) // 2:] + neg[len(neg) // 2:]
    grid = [t / 100 for t in range(30, 96, 5)]
    best = max(grid, key=lambda t: prf(dev, gold, jev, t)["f05"])
    # Hand-off-only view: false alarms on well-specified hand-offs are the failure users see.
    hand_test = [i for i in test if i.startswith("h")]
    report = {
        "items": len(ids), "gold_ambiguous": len(pos),
        "kappa_main": round(k1, 3), "kappa_handoff": round(k2, 3),
        "unanimous_handoff": f"{u2}/60",
        "chosen_AMBIGUITY_MIN": best,
        "dev": prf(dev, gold, jev, best),
        "test": prf(test, gold, jev, best),
        "test_old_0.7": prf(test, gold, jev, 0.7),
        "test_handoffs_only": prf(hand_test, gold, jev, best),
        "test_handoffs_only_old_0.7": prf(hand_test, gold, jev, 0.7),
        "dev_curve": {t: prf(dev, gold, jev, t) for t in grid},
    }
    (HERE / "report_ambiguity.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "dev_curve"}, indent=2))


if __name__ == "__main__":
    main()
