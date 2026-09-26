#!/usr/bin/env python3
"""Classifier evaluation for the effort tips.

Protocol (fixed before looking at results):
- Gold label = majority of 3 blind raters; items with no majority are dropped.
- Stratified 50/50 dev/test split by gold level, seed 0.
- Current effort is assumed to be `medium` (Opus 5.5's default).
- CONFIDENCE_MIN and AMBIGUITY_MIN are chosen on dev only, maximising F0.5 of
  tips (precision-weighted: a wrong tip is worse than a missed one).
- The test split is scored once with the chosen thresholds.

  python3 eval/analyze.py            # uses cached Jev outputs, calls API for missing
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "plugins" / "spending-effort-with-jev" / "scripts"))
import effort_advisor as ea  # noqa: E402
# Dev scripts: pass the developer's key to the plugin the way Claude Code would.
import os  # noqa: E402
os.environ.setdefault("CLAUDE_PLUGIN_OPTION_TYPESAFE_API_KEY", os.environ.get("TYPESAFE_API_KEY", ""))

LEVELS = ["low", "medium", "high", "max", "unclear"]
CURRENT = "medium"


def load(name):
    return [json.loads(l) for l in (HERE / name).read_text().splitlines() if l.strip()]


def jev_outputs(prompts):
    cache_f = HERE / "jev_outputs.jsonl"
    cache = {r["id"]: r for r in load("jev_outputs.jsonl")} if cache_f.exists() else {}
    key = ea.api_key()
    with open(cache_f, "a") as f:
        for p in prompts:
            if p["id"] in cache:
                continue
            a = ea.ask_jev(key, p["prompt"], p["context"])
            rec = {"id": p["id"], "answers": a}
            cache[p["id"]] = rec
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {k: v["answers"] for k, v in cache.items()}


def fleiss_kappa(rows, cats):
    n = len(rows[0])
    N = len(rows)
    p_j = [sum(r.count(c) for r in rows) / (N * n) for c in cats]
    P_i = [(sum(r.count(c) ** 2 for c in cats) - n) / (n * (n - 1)) for r in rows]
    P_bar, P_e = sum(P_i) / N, sum(p * p for p in p_j)
    return (P_bar - P_e) / (1 - P_e) if P_e < 1 else 1.0


def gold(prompts):
    raters = [{r["id"]: r for r in load(f"labels_r{i}.jsonl")} for i in (1, 2, 3)]
    out, lvl_rows, amb_rows = {}, [], []
    for p in prompts:
        ls = [r[p["id"]]["level"] for r in raters]
        am = [bool(r[p["id"]]["handoff_ambiguous"]) for r in raters]
        lvl_rows.append(ls)
        amb_rows.append(am)
        top, cnt = Counter(ls).most_common(1)[0]
        if cnt >= 2:
            out[p["id"]] = {"level": top, "unanimous": cnt == 3,
                            "ambiguous": sum(am) >= 2}
    kappa_lvl = fleiss_kappa(lvl_rows, LEVELS)
    kappa_amb = fleiss_kappa(amb_rows, [True, False])
    return out, kappa_lvl, kappa_amb


def split(gold_map, seed=0):
    by = {}
    for pid, g in sorted(gold_map.items()):
        by.setdefault(g["level"], []).append(pid)
    rng = random.Random(seed)
    dev, test = [], []
    for lvl, ids in sorted(by.items()):
        rng.shuffle(ids)
        h = len(ids) // 2
        dev += ids[:h]
        test += ids[h:]
    return dev, test


def score(ids, gold_map, jev, conf_min, amb_min):
    ea.CONFIDENCE_MIN, ea.AMBIGUITY_MIN = conf_min, amb_min
    tips = correct = should = caught = 0
    amb_tp = amb_fp = amb_fn = 0
    top1 = 0
    for pid in ids:
        g, a = gold_map[pid], jev[pid]
        top1 += a["effort"]["choice"] == g["level"]
        s = ea.suggestion(a, CURRENT)
        # A tip is "needed" when gold is a real level not within one rank of current.
        need = g["level"] not in ("unclear",) and abs(ea.RANK[g["level"]] - ea.RANK[CURRENT]) >= 1
        want_amb = g["ambiguous"]
        if s == "ambiguous":
            amb_tp += want_amb
            amb_fp += not want_amb
        elif want_amb:
            amb_fn += 1
        if s not in (None, "ambiguous"):
            tips += 1
            correct += s == g["level"]
        if need:
            should += 1
            caught += s == g["level"]
    prec = correct / tips if tips else 1.0
    rec = caught / should if should else 1.0
    b2 = 0.25
    f05 = (1 + b2) * prec * rec / (b2 * prec + rec) if prec + rec else 0.0
    amb_p = amb_tp / (amb_tp + amb_fp) if amb_tp + amb_fp else 1.0
    amb_r = amb_tp / (amb_tp + amb_fn) if amb_tp + amb_fn else 1.0
    return {"n": len(ids), "top1_acc": top1 / len(ids), "tips_shown": tips,
            "tip_precision": prec, "tip_recall": rec, "tip_f05": f05,
            "ambiguity_precision": amb_p, "ambiguity_recall": amb_r,
            "ambiguity_tips": amb_tp + amb_fp}


def confusion(ids, gold_map, jev):
    m = {g: Counter() for g in LEVELS}
    for pid in ids:
        m[gold_map[pid]["level"]][jev[pid]["effort"]["choice"]] += 1
    return {g: dict(c) for g, c in m.items() if c}


def main():
    prompts = load("prompts.jsonl")
    gold_map, k_lvl, k_amb = gold(prompts)
    jev = jev_outputs(prompts)
    dev, test = split(gold_map)
    grid = [(c / 100, a / 100) for c in range(40, 96, 5) for a in range(50, 96, 5)]
    best = max(grid, key=lambda t: (round(score(dev, gold_map, jev, *t)["tip_f05"], 4),
                                    round(score(dev, gold_map, jev, *t)["ambiguity_precision"], 4)))
    # Ambiguity threshold tuned separately: maximise F0.5 of ambiguity tips on dev.
    def amb_f05(a):
        s = score(dev, gold_map, jev, best[0], a)
        p, r = s["ambiguity_precision"], s["ambiguity_recall"]
        return (1.25 * p * r / (0.25 * p + r)) if p + r else 0
    best_amb = max(range(50, 96, 5), key=lambda a: amb_f05(a / 100)) / 100
    chosen = (best[0], best_amb)
    report = {
        "items": len(prompts), "with_majority": len(gold_map),
        "unanimous": sum(g["unanimous"] for g in gold_map.values()),
        "gold_level_counts": dict(Counter(g["level"] for g in gold_map.values())),
        "gold_ambiguous": sum(g["ambiguous"] for g in gold_map.values()),
        "fleiss_kappa_level": round(k_lvl, 3), "fleiss_kappa_ambiguous": round(k_amb, 3),
        "dev_n": len(dev), "test_n": len(test),
        "chosen_thresholds": {"CONFIDENCE_MIN": chosen[0], "AMBIGUITY_MIN": chosen[1]},
        "old_thresholds_test": score(test, gold_map, jev, 0.6, 0.7),
        "dev": score(dev, gold_map, jev, *chosen),
        "test": score(test, gold_map, jev, *chosen),
        "test_confusion_gold_to_jev": confusion(test, gold_map, jev),
    }
    (HERE / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
