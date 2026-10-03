"""The mod's judgement (plugins/.../hooks/judge.ts) against the Python hook
the eval measured (python/effort_advisor.py): same inputs, same verdicts,
same request to Jev, same context. Needs bun; skipped without it.
Run: python3 -m unittest tests.test_parity

The conversation is generated the way each side reads it: transcript
entries for the hook, and for the mod the rows Claude Code builds from them
(isMeta messages left out, a message's text blocks joined with nothing
between them).

Known, intended differences (not generated here):
- Only what a person typed is judged (origin composer or bridge); the hook
  also judged `claude -p`/SDK turns, scheduled prompts and other sessions'
  messages unless they started with a wrapper tag.
- The rows join a message's text blocks with nothing between them, so the mod
  drops Claude Code's own tags (<system-reminder>, <command-name>, ...: names
  with a hyphen or underscore) wherever they are, where the hook dropped any
  block starting with "<". A person's own <b>...</b> stays. Claude's replies
  are kept as written. Two text blocks of a person's own words in one message
  run together.
- `[Image: ...]` and `[Request interrupted by user...]` markers are removed
  as spans; the hook dropped lines starting with "[Image: source:" or
  "[Request interrupted".
- A compaction summary and, in case an engine keeps them, messages starting
  like Claude Code's notices are dropped from a person's turns by how they
  start; the hook used the transcript's isMeta / isCompactSummary flags.
- The mod refuses true/false where Jev's answer has a number (the hook took
  them as 1/0), and `probabilities` that is no object, like [] or 0 (the
  hook took an empty value as missing).
"""
import io
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import effort_advisor as ea  # noqa: E402

KEYS = ["low", "medium", "high", "max", "unclear"]
CURRENTS = [None, "low", "medium", "high", "xhigh", "max", "auto", "toString"]


def random_answers(rng):
    keys = rng.sample(KEYS, rng.randint(1, 5))
    weights = [rng.choice([0, rng.random(), rng.random() ** 3, 1]) for _ in keys]
    total = sum(weights) or 1
    probs = {k: w / total for k, w in zip(keys, weights)}
    if rng.random() < 0.5:  # Jev rounds; rounding lands on the thresholds
        probs = {k: round(v, rng.choice([1, 2, 4])) for k, v in probs.items()}
    choice = max(probs, key=probs.get) if rng.random() < 0.8 else rng.choice(KEYS)
    conf = probs.get(choice, 0) if rng.random() < 0.9 else rng.choice([None, 0, 0.5, 0.95])
    if rng.random() < 0.08:
        probs = rng.choice([None, {}])  # older answers: confidence only
    noul = rng.choice([0.0, 0.0, 0.0, rng.random(), 0.69, 0.7, 0.71])
    return {"effort": {"choice": choice, "confidence": conf, "probabilities": probs},
            "handoff_ambiguous": {"noul": noul}}


THRESHOLD_CASES = [
    ({"high": 0.7, "low": 0.3}, "low"), ({"low": 0.7, "high": 0.3}, "max"),
    ({"medium": 0.35, "high": 0.35, "low": 0.3}, "low"), ({"unclear": 0.5, "high": 0.5}, "low"),
    ({"low": 0.35, "unclear": 0.35, "max": 0.3}, "low"), ({"high": 0.5, "max": 0.5}, "xhigh"),
    ({"max": 0.7, "medium": 0.3}, None), ({"low": 0.1, "medium": 0.2, "high": 0.3, "max": 0.4}, "medium"),
]

CHECKED_CASES = [
    {"effort": {"choice": "high", "confidence": 0.9, "probabilities": {"high": 0.9, "low": 0.1}},
     "handoff_ambiguous": {"noul": 0}},
    {"effort": {"choice": "unclear", "confidence": 0.6}, "handoff_ambiguous": {"noul": 0.1}},
    {"effort": {"choice": "high"}},
    {"effort": {"choice": "huge", "confidence": 0.9}, "handoff_ambiguous": {"noul": 0}},
    {"effort": {"choice": "high", "confidence": None, "probabilities": ["x"]}, "handoff_ambiguous": {"noul": 0}},
    {"effort": {"choice": "high", "confidence": 0.9}, "handoff_ambiguous": {"noul": None}},
    {"effort": {"choice": "high", "confidence": None}, "handoff_ambiguous": {"noul": 0}},
    {"effort": {"choice": "toString", "confidence": 0.9}, "handoff_ambiguous": {"noul": 0}},
    {"effort": {"choice": "high", "confidence": 0.9, "probabilities": {"high": "0.9"}}, "handoff_ambiguous": {"noul": 0}},
    {"handoff_ambiguous": {"noul": 0}},
    [], None, "answers",
]

PROMPTS = [
    "ok", "OK.", "  继续！ ", "go ahead!!", "continue~", "Continue。", "ok, fix it", "lgtm",
    "sounds good.", "Do it", "do it now", "好的～", "可以。", "开始吧", "yes please", "",
    "/effort high", "/spending-effort-with-jev:high go", "/Users/x/app.py crashes on start",
    "<task-notification><task-id>1</task-id></task-notification>", "<local-command-stdout>hi</local-command-stdout>",
    "<command-name>/model</command-name>", "why does <b>x</b> fail?", "fix the flaky test",
    "/修复 bug", "/über test", "/ x",
]


def random_text(rng, size):
    alphabet = rng.choice(["ascii", "cjk", "emoji", "mixed"])
    pick = {
        "ascii": lambda: rng.choice("abcdefghij klmnop .,?\n"),
        "cjk": lambda: rng.choice("修复这个测试为什么会失败呢，。"),
        "emoji": lambda: rng.choice("😀🚀✓ a"),
        "mixed": lambda: rng.choice("abc 修复😀 ?\n"),
    }[alphabet]
    return "".join(pick() for _ in range(size)).strip() or "x"


def random_conversation(rng):
    """One conversation as transcript entries (the hook) and the rows Claude Code builds from them (the mod)."""
    entries, rows = [], []
    for i in range(rng.randint(0, 14)):
        role = rng.choice(["user", "assistant"])
        flags, blocks, tool_results = {}, [], False
        kind = rng.random()
        size = rng.choice([5, 40, 400, 2000, 5000])
        if role == "assistant":
            blocks = [] if kind < 0.15 else [random_text(rng, size)]  # [] = only tool calls
            content = [{"type": "text", "text": b} for b in blocks]
            if kind < 0.4:
                content.append({"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {}})
        elif kind < 0.15:
            tool_results = True
            flags["toolUseResult"] = {"stdout": "ok"}
            content = [{"type": "tool_result", "tool_use_id": f"t{i}", "content": "ok"}]
        elif kind < 0.25:
            flags["isMeta"] = True
            blocks = [rng.choice([
                "Base directory for this skill: /Users/me/.claude/skills/x\n\n# Skill\nDo things.",
                "Another Claude session sent a message: <agent-message>done</agent-message>",
                "[Image: original 2080x832, displayed at 2000x800. Multiply coordinates by 1.04]",
                "Your response above was cut off mid-stream. Resume from where it stopped.",
            ])]
            content = [{"type": "text", "text": b} for b in blocks]
        elif kind < 0.3:
            flags["isCompactSummary"] = True
            blocks = ["This session is being continued from a previous conversation that ran out of context. ..."]
            content = [{"type": "text", "text": b} for b in blocks]
        else:
            blocks = [random_text(rng, size)]
            extra = rng.random()
            if extra < 0.2:
                blocks.insert(0, "<system-reminder>\nToday is Monday.\n</system-reminder>")
            elif extra < 0.3:
                blocks.append("<system-reminder>Be brief.</system-reminder>")
            elif extra < 0.4:
                blocks.insert(0, "[Request interrupted by user]")
            elif extra < 0.5:
                blocks[-1] += '\n<pasted_content id="p">pasted log line</pasted_content>'
            elif extra < 0.55:
                blocks = ["<command-name>/shuorenhua</command-name>\n<command-message>shuorenhua</command-message>"]
            elif extra < 0.6:
                blocks.append("[Image: source: /tmp/shot.png]")
            content = [{"type": "text", "text": b} for b in blocks]
        entry = {"uuid": f"u{i}", "parentUuid": f"u{i - 1}" if i else None, "type": role,
                 "message": {"role": role, "content": content}, **flags}
        entries.append(entry)
        if flags.get("isMeta"):
            continue  # Claude Code leaves isMeta messages out of the rows
        row = {"role": role, "text": "".join(blocks)}
        if tool_results:
            row["toolResults"] = [{"tool_use_id": f"t{i}", "text": "ok"}]
        rows.append(row)
    return entries, rows


def python_body(prompt, turns):
    """The request the hook sends, captured at the network."""
    sent = {}

    class Opener:
        def open(self, req, timeout):
            sent["body"] = json.loads(req.data)
            answer = {"answers": CHECKED_CASES[0]}
            return io.BytesIO(json.dumps(answer).encode())

    with mock.patch.object(urllib.request, "build_opener", lambda *a: Opener()):
        ea.ask_jev("k", prompt, turns)
    return sent["body"]


@unittest.skipUnless(shutil.which("bun"), "bun runs the mod's TypeScript")
class Parity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = random.Random(0)
        cls.verdicts = [(random_answers(rng), rng.choice(CURRENTS)) for _ in range(5000)]
        cls.verdicts += [({"effort": {"choice": max(p, key=p.get), "confidence": max(p.values()), "probabilities": p},
                           "handoff_ambiguous": {"noul": 0}}, cur) for p, cur in THRESHOLD_CASES]
        cls.texts = [random_text(rng, rng.choice([10, 100, 1000])) for _ in range(200)]
        conversations = [random_conversation(rng) for _ in range(400)]
        cls.budgets = [rng.choice([0, 200, 1500, 6000]) for _ in conversations]
        cls.entries = [e for e, _ in conversations]
        turn_lists = [[{"role": r["role"], "text": r["text"]} for r in rows[-4:] if r["text"]]
                      for _, rows in conversations[:60]]
        prompts = ["fix it", "a" * 100_000, "修" * 30_000, "😀" * 25_000, "ok, and add a test"]
        cls.bodies = [(prompts[i % len(prompts)], turns) for i, turns in enumerate(turn_lists)]
        cases = {
            "verdicts": cls.verdicts, "checked": CHECKED_CASES, "prompts": PROMPTS, "texts": cls.texts,
            "bodies": cls.bodies, "conversations": [[rows, b] for (_, rows), b in zip(conversations, cls.budgets)],
        }
        run = subprocess.run(["bun", str(ROOT / "tests" / "parity.ts")], input=json.dumps(cases),
                             capture_output=True, text=True, timeout=120)
        if run.returncode != 0:
            raise RuntimeError(run.stderr)
        cls.ts = json.loads(run.stdout)

    def test_verdicts(self):
        for (answers, current), (kind, level, share) in zip(self.verdicts, self.ts["verdicts"]):
            py_kind, py_level, py_share = ea.verdict(answers, current)
            with self.subTest(answers=answers, current=current):
                self.assertEqual((kind, level), (py_kind, py_level))
                self.assertAlmostEqual(share, py_share, places=12)

    def test_malformed_answers(self):
        def accepted(raw):
            try:
                ea.checked(raw)
                return True
            except Exception:
                return False
        self.assertEqual(self.ts["checked"], [accepted(raw) for raw in CHECKED_CASES])

    def test_what_is_judged(self):
        expected = [[ea.typed(p.strip()), p.strip().lower().strip(" \t\n.!。！~～") in ea.GO_AHEADS] for p in PROMPTS]
        self.assertEqual(self.ts["prompts"], expected)

    def test_token_estimates_and_caps(self):
        self.assertEqual(self.ts["tokens"], [[ea.est_tokens(t), ea.cap_tokens(t, 50)] for t in self.texts])

    def test_request_to_jev(self):
        for (prompt, turns), body in zip(self.bodies, self.ts["bodies"]):
            with self.subTest(prompt=prompt[:20], turns=len(turns)):
                self.assertEqual(body, python_body(prompt, turns))

    def test_context_from_the_conversation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            for entries, budget, turns in zip(self.entries, self.budgets, self.ts["turns"]):
                path.write_text("".join(json.dumps(e) + "\n" for e in entries))
                with self.subTest(entries=len(entries), budget=budget):
                    self.assertEqual(turns, ea.recent_turns(str(path), wait_s=0, budget=budget))


if __name__ == "__main__":
    unittest.main()
