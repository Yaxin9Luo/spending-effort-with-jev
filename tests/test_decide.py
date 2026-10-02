"""Offline tests. Run: python3 -m unittest discover tests"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
import unicodedata
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "spending-effort-with-jev" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import effort_advisor as ea  # noqa: E402
import statusline  # noqa: E402


def answers(choice, conf=0.9, amb=0.0, probs=None):
    """Jev's answer; by default the rest of the probability is spread evenly."""
    if probs is None:
        others = [lv for lv in ("low", "medium", "high", "max") if lv != choice]
        probs = {lv: round((1 - conf) / len(others), 4) for lv in others}
        probs[choice] = conf
    return {"effort": {"type": "choice", "choice": choice, "confidence": conf,
                       "probabilities": probs},
            "handoff_ambiguous": {"type": "noul", "noul": amb}}


def split(**probs):
    """An answer whose top choice is the most probable level."""
    top = max(probs, key=probs.get)
    return answers(top, probs[top], probs=probs)


def width(text):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


class Suggestion(unittest.TestCase):
    def test_suggests_when_levels_differ(self):
        self.assertEqual(ea.suggestion(answers("high"), "low"), "high")

    def test_none_when_same_level(self):
        self.assertIsNone(ea.suggestion(answers("medium"), "medium"))

    def test_xhigh_counts_as_close_to_high_and_max(self):
        self.assertIsNone(ea.suggestion(answers("high"), "xhigh"))
        self.assertIsNone(ea.suggestion(answers("max"), "xhigh"))

    def test_none_when_unclear_or_unsure(self):
        self.assertIsNone(ea.suggestion(answers("unclear", 0.99), "low"))
        self.assertIsNone(ea.suggestion(split(low=0.45, high=0.45, medium=0.1), "low"))

    def test_neighbouring_levels_splitting_the_vote_is_a_fit(self):
        # Regression: low 0.52 / unclear 0.33 on low said "not sure".
        self.assertEqual(ea.verdict(split(low=0.52, unclear=0.33, high=0.15), "low")[0], "match")
        # xhigh sits between high and max, so a high/max split fits it.
        self.assertEqual(ea.verdict(split(high=0.5, max=0.4, medium=0.1), "xhigh")[0], "match")
        # One level away is a switch, so staying vs. switching split evenly is unsure.
        self.assertEqual(ea.verdict(split(medium=0.45, low=0.41, high=0.14), "low")[0], "unsure")

    def test_switch_needs_most_of_the_probability_on_one_side(self):
        kind, level, share = ea.verdict(split(high=0.5, max=0.35, low=0.15), "low")
        self.assertEqual((kind, level), ("up", "high"))
        self.assertAlmostEqual(share, 0.85)
        self.assertEqual(ea.verdict(split(high=0.6, low=0.4), "low")[0], "unsure")
        self.assertEqual(ea.verdict(split(low=0.9, medium=0.1), "max")[:2], ("down", "low"))

    def test_first_message_uses_the_top_choice(self):
        self.assertEqual(ea.verdict(split(high=0.8, low=0.2), None)[:2], ("fits", "high"))
        self.assertEqual(ea.verdict(split(high=0.5, low=0.5), None)[0], "unsure")


class Status(unittest.TestCase):
    def kind(self, *args, **kw):
        return ea.status(*args, **kw)[0]

    def test_kinds(self):
        self.assertEqual(self.kind(answers("high"), "low"), "up")
        self.assertEqual(self.kind(answers("low"), "max"), "down")
        self.assertEqual(self.kind(answers("medium"), "medium"), "match")
        self.assertEqual(self.kind(answers("high"), None), "fits")
        self.assertEqual(self.kind(split(high=0.5, low=0.5), "low"), "unsure")
        self.assertEqual(self.kind(answers("unclear", 0.99), "low"), "unclear")
        self.assertEqual(self.kind(answers("max", amb=0.9), "low"), "ambiguous")

    def test_up_line_says_what_to_do(self):
        text = ea.status(answers("high", 0.98), "low")[1]
        self.assertIn("needs high", text)
        self.assertIn("was low", text)
        self.assertIn("/effort high", text)

    def test_live_level_worded_as_now(self):
        self.assertIn("now low", ea.status(answers("high"), "low", "live")[1])
        self.assertIn("you're on high", ea.status(answers("high"), "high", "live")[1])

    def test_fit_line_names_the_need_and_the_compared_level(self):
        # Regression: "✓ low fits · same as last turn" read as "you're on low"
        # after the user had switched to high in the desktop bar.
        text = ea.status(split(low=0.9, medium=0.1), "low")[1]
        self.assertIn("low fits this", text)
        self.assertIn("last turn ran on low", text)

    def test_stop_step_worded_per_client(self):
        self.assertIn("→ Esc,", ea.status(answers("high"), "low")[1])
        self.assertIn("→ stop, set high in the bar", ea.status(answers("high"), "low", desktop=True)[1])
        self.assertIn("→ set low in the bar", ea.status(answers("low"), "max", desktop=True)[1])

    def test_client_detected_from_entrypoint(self):
        env = dict(os.environ)
        try:
            os.environ["CLAUDE_CODE_ENTRYPOINT"] = "claude-desktop"
            self.assertTrue(ea.in_desktop_app())
            os.environ["CLAUDE_CODE_ENTRYPOINT"] = "cli"
            self.assertFalse(ea.in_desktop_app())
        finally:
            os.environ.clear()
            os.environ.update(env)

    def test_ask_mode_changes_the_up_line(self):
        self.assertIn("check with you", ea.status(answers("high"), "low", ask=True)[1])

    def test_no_backticks_and_lines_fit_a_terminal(self):
        # Notices are plain text, and Claude Code adds a ~28-column prefix.
        for lg in ("en", "zh"):
            for rec in ("low", "medium", "high", "max", "unclear"):
                for cur in (None, "low", "medium", "high", "xhigh", "max"):
                    for src in ("turn", "live"):
                        for ask in (False, True):
                            for conf, amb in ((0.99, 0), (0.5, 0), (0.99, 0.9)):
                                for desktop in (False, True):
                                    text = ea.status(answers(rec, conf, amb), cur, src, lg,
                                                     ask, desktop=desktop)[1]
                                    self.assertNotIn("`", text)
                                    # The terminal wraps at its width; the desktop app reflows.
                                    self.assertLessEqual(width(text), 84 if desktop else 76, text)

    def test_chinese(self):
        self.assertIn("需要 high", ea.status(answers("high"), "low", language="zh")[1])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        ea.STATE_DIR = self.tmp
        self._ask, self._key, self._env = ea.ask_jev, ea.api_key, dict(os.environ)
        ea.api_key = lambda: "k"
        for k in list(os.environ):
            if k.startswith("CLAUDE_PLUGIN_OPTION_") or k == "CLAUDE_CODE_ENTRYPOINT":
                del os.environ[k]

    def tearDown(self):
        ea.ask_jev, ea.api_key = self._ask, self._key
        os.environ.clear()
        os.environ.update(self._env)

    def event(self, data):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            {"UserPromptSubmit": ea.on_prompt, "Stop": ea.on_stop,
             "PostModelSwitch": ea.on_model_switch,
             "SessionStart": ea.on_session_start}[data["hook_event_name"]](data)
        return json.loads(buf.getvalue()) if buf.getvalue() else None

    def prompt(self, choice, conf=0.9, text="do the thing", amb=0.0):
        ea.ask_jev = lambda *a: answers(choice, conf, amb)
        time.sleep(0.002)  # keep state timestamps strictly ordered
        return self.event({"hook_event_name": "UserPromptSubmit",
                           "session_id": "s", "prompt": text})

    def line(self, *args, **kw):
        out = self.prompt(*args, **kw)
        return out["systemMessage"] if out else None

    def stop(self, level, **extra):
        time.sleep(0.002)
        return self.event({"hook_event_name": "Stop", "session_id": "s",
                           "effort": {"level": level} if level else None, **extra})


class Flow(Base):
    def test_first_message_has_no_comparison(self):
        self.assertIn("fits this", self.line("high"))

    def test_every_message_gets_a_line(self):
        self.stop("medium")
        self.assertIn("last turn ran on", self.line("medium"))
        self.stop("medium")
        self.assertIn("/effort high", self.line("high"))

    def test_stop_prints_nothing(self):
        self.assertIsNone(self.stop("low"))

    def test_stop_ignores_subagents_and_missing_level(self):
        self.stop("low")
        self.stop("max", agent_id="sub1")
        self.stop(None)
        self.assertEqual(ea.current_level("s"), ("low", "turn"))

    def test_after_an_interrupted_tip_nothing_is_compared(self):
        self.stop("low")
        self.assertIn("/effort high", self.line("high"))
        # Esc: no Stop. The user switches with /effort (invisible) and resends.
        self.assertIn("fits this", self.line("high", text="fix the pagination bug"))
        self.stop("high")
        self.assertIn("last turn ran on", self.line("high"))

    def test_completed_tip_turn_is_compared_normally(self):
        self.stop("low")
        self.line("high")
        self.stop("low")  # the user let it run
        self.assertIn("was low", self.line("high"))

    def test_ask_mode(self):
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.stop("low")
        out = self.prompt("high")
        # Regression: the line used to point from the last turn's level ("⬆ … was
        # low") even when the user had already changed it; Claude checks instead.
        self.assertIn("Claude will check your level", out["systemMessage"])
        self.assertNotIn("⬆", out["systemMessage"])
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("/effort high", ctx)
        self.assertIn("wait", ctx)
        # Regression: the level compared with is the last turn's; the user may
        # have switched since, so Claude reads the live level before asking.
        self.assertIn("echo $CLAUDE_EFFORT", ctx)
        self.stop("low", last_assistant_message="This looks like a high-effort task and you're on low. Switch first?")  # Claude asked and stopped
        # The user may have switched since, so the next message isn't compared.
        self.assertIn("fits this", self.line("high", text="switched, go"))
        self.stop("high")
        self.assertIn("last turn ran on", self.line("high"))

    def test_ask_turn_interrupted_does_not_suppress_twice(self):
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.stop("low")
        self.prompt("high")          # Claude would ask...
        self.line("high")            # ...but the user hit Esc and resent
        self.stop("high")
        self.assertIn("last turn ran on", self.line("high"))

    def test_ask_mode_covers_downgrades(self):
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.stop("max")
        out = self.prompt("low")
        self.assertIn("Claude will check your level", out["systemMessage"])
        self.assertIn("/effort low", out["hookSpecificOutput"]["additionalContext"])
        self.stop("max", last_assistant_message="Low is enough for this. Switch to low?")
        self.assertIn("fits this", self.line("low", text="switched, go"))

    def test_quiet_mode_only_shows_switches(self):
        os.environ["CLAUDE_PLUGIN_OPTION_QUIET"] = "true"
        self.stop("medium")
        self.assertIsNone(self.prompt("medium"))
        self.assertIsNone(self.prompt("unclear", 0.99))
        self.stop("medium")
        self.assertIn("/effort high", self.line("high"))

    def test_go_aheads_answered_without_calling_jev(self):
        def boom(*a):
            raise AssertionError("Jev should not be called")
        for text in ("ok", "Continue.", "go ahead", "继续", "好的！"):
            ea.ask_jev = boom
            out = self.event({"hook_event_name": "UserPromptSubmit",
                              "session_id": "s", "prompt": text})
            self.assertIn("go-ahead", out["systemMessage"], text)
            self.assertNotIn("hookSpecificOutput", out)

    def test_go_ahead_with_ask_first_hands_sizing_to_claude(self):
        # Regression: "继续" after a planning chat said "nothing to judge",
        # though it started hard work the user was on low for.
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        ea.ask_jev = lambda *a: (_ for _ in ()).throw(AssertionError("no Jev call"))
        out = self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "继续"})
        self.assertIn("Claude will size", out["systemMessage"])
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("echo $CLAUDE_EFFORT", ctx)
        self.assertIn("turned down a switch in the same direction", ctx)
        self.assertIn(ea.EFFORT_CRITERIA["max"], ctx)
        # Claude may ask, so the level recorded at the end of this turn isn't trusted.
        self.assertTrue(ea.read_json(ea.state_file("tip", "s"))["asked"])

    def test_unplaceable_go_ahead_with_context_goes_to_claude(self):
        # Regression: "好，提交 spec，开始第 0 阶段" — Jev saw only "I'll commit
        # the spec and start phase 0" and answered unclear.
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.stop("low", last_assistant_message="Anything else? If not, I'll commit the spec and start phase 0.")
        out = self.prompt("unclear", 0.55, text="OK, commit the spec and start phase 0")
        self.assertIn("echo $CLAUDE_EFFORT", out["hookSpecificOutput"]["additionalContext"])

    def test_repeated_tip_is_short_after_the_user_stayed(self):
        self.stop("low")
        self.assertIn("Esc", self.line("high"))
        self.stop("low")  # let it run on low
        again = self.line("high")
        self.assertIn("needs high", again)
        self.assertIn("was low", again)
        self.assertNotIn("Esc", again)
        self.stop("low")
        # Same direction from the same level: still brief, though Jev's pick moved.
        again = self.line("max")
        self.assertIn("needs max", again)
        self.assertNotIn("Esc", again)

    def test_ask_mode_asks_once_per_situation(self):
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.stop("low")
        self.assertIn("hookSpecificOutput", self.prompt("high"))
        self.stop("low", last_assistant_message="This looks like a high-effort task and you're on low. Switch first?")
        out = self.prompt("high", text="go ahead as is")  # after the ask: Claude rechecks
        self.assertIn("turned down a switch", out["hookSpecificOutput"]["additionalContext"])
        self.stop("low", last_assistant_message="Fixed: the loop was off by one. " * 30)
        out = self.prompt("high")                         # the user stayed on low
        self.assertNotIn("hookSpecificOutput", out)
        self.assertIn("was low", out["systemMessage"])

    def test_go_ahead_answer_keeps_the_stay(self):
        # Regression: answering Claude's question with "go ahead" / "ok" erased
        # the record that the user chose to stay, so Claude asked again.
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.stop("low")
        self.prompt("high")
        self.stop("low", last_assistant_message="This looks like a high-effort task and you're on low. Switch first?")
        self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "go ahead"})
        self.stop("low", last_assistant_message="Done. " * 200)
        out = self.prompt("high", text="now the next bug")
        self.assertNotIn("hookSpecificOutput", out)
        self.assertIn("was low", out["systemMessage"])

    def test_check_turn_that_just_worked_keeps_the_level(self):
        # After a check where Claude found the level fine and did the work,
        # the next message is compared again instead of staying unknown.
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.prompt("high")                                   # first message: check
        self.stop("high", last_assistant_message="Done. " * 200)
        self.assertIn("last turn ran on high", self.line("high"))

    def test_extra_stop_keeps_the_question_open(self):
        # Regression: a second Stop with no prompt in between (a background
        # task waking Claude) dropped after_ask, so the next message was
        # compared with the level the user had been asked to leave.
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.stop("low")
        self.prompt("high")
        self.stop("low", last_assistant_message="This looks like a high-effort task and you're on low. Switch first?")
        self.stop("low", last_assistant_message="Background task finished.")
        self.assertIn("fits this", self.line("high", text="I switched to high, go"))

    def test_slash_commands_skipped(self):
        self.assertIsNone(self.prompt("high", text="/effort high"))

    def test_jev_failure_gives_a_line(self):
        def boom(*a):
            raise TimeoutError
        ea.ask_jev = boom
        out = self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "x"})
        self.assertIn("no tip", out["systemMessage"])

    def test_rejected_key(self):
        class HTTPError(Exception):
            code = 401
        def reject(*a):
            raise HTTPError
        ea.ask_jev = reject
        out = self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "x"})
        self.assertIn("rejected", out["systemMessage"])

    def test_no_key_told_once(self):
        ea.api_key = lambda: None
        first = self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "x"})
        second = self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "x"})
        self.assertIn("no TypeSafe API key", first["systemMessage"])
        self.assertIsNone(second)

    def test_model_switch_forgets_level(self):
        self.stop("low")
        self.event({"hook_event_name": "PostModelSwitch", "session_id": "s"})
        self.assertEqual(ea.current_level("s"), (None, "unknown"))


class StatusLine(Base):
    def test_live_level_preferred_while_newer_than_last_turn(self):
        self.stop("low")
        time.sleep(0.002)
        ea.write_json(ea.state_file("live", "s"), {"level": "high", "t": time.time()})
        self.assertEqual(ea.current_level("s"), ("high", "live"))
        self.stop("medium")  # status line no longer updating: fall back
        self.assertEqual(ea.current_level("s"), ("medium", "turn"))

    def test_segment(self):
        self.assertEqual(statusline.segment("low", None), "effort low")
        self.assertEqual(statusline.segment("low", {"kind": "up", "rec": "high", "conf": 0.9}),
                         "effort low · Jev: high ⬆")
        self.assertEqual(statusline.segment("high", {"kind": "up", "rec": "high", "conf": 0.9}),
                         "effort high ✓")
        self.assertEqual(statusline.segment("max", {"kind": "fits", "rec": "low", "conf": 0.9}),
                         "effort max · Jev: low ⬇")
        self.assertEqual(statusline.segment("low", {"kind": "unsure", "rec": "high", "conf": 0.5}),
                         "effort low")
        self.assertEqual(statusline.segment(None, None), "")

    def test_statusline_records_live_level(self):
        data = json.dumps({"session_id": "s", "effort": {"level": "xhigh"}})
        sys.stdin = io.StringIO(data)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                statusline.main()
        finally:
            sys.stdin = sys.__stdin__
        self.assertEqual(ea.current_level("s"), ("xhigh", "live"))


class SessionStart(Base):
    def test_prunes_old_state_and_copies_statusline(self):
        old = self.tmp / "turn-old.json"
        old.write_text("{}")
        os.utime(old, (0, 0))
        fresh = self.tmp / "turn-new.json"
        fresh.write_text("{}")
        legacy = self.tmp / "pending-abc.json"
        legacy.write_text("{}")
        self.event({"hook_event_name": "SessionStart", "session_id": "s"})
        self.assertFalse(old.exists())
        self.assertFalse(legacy.exists())
        self.assertTrue(fresh.exists())
        self.assertTrue((self.tmp / "bin" / "statusline.py").exists())
        self.assertTrue((self.tmp / "bin" / "effort_advisor.py").exists())


class Context(Base):
    def write(self, path, entries):
        path.write_text("".join(json.dumps(e) + "\n" for e in entries))

    def msg(self, uuid, parent, role, text):
        return {"uuid": uuid, "parentUuid": parent, "type": role,
                "message": {"role": role, "content": text}}

    def test_follows_the_live_branch_after_a_rewind(self):
        f = self.tmp / "t.jsonl"
        self.write(f, [self.msg("a", None, "user", "fix the bug"),
                       self.msg("b", "a", "assistant", "old answer, rewound away"),
                       self.msg("c", "a", "assistant", "kept answer"),
                       self.msg("d", "c", "user", "now add a test")])
        texts = [t["text"] for t in ea.recent_turns(str(f))]
        self.assertEqual(texts, ["fix the bug", "kept answer", "now add a test"])

    def test_user_messages_whole_replies_trimmed_to_their_end(self):
        f = self.tmp / "long.jsonl"
        long_user = "please " * 2000
        self.write(f, [self.msg("a", None, "user", long_user),
                       self.msg("b", "a", "assistant", "x" * 5000 + " OLD END"),
                       self.msg("c", "b", "user", "ok and then?"),
                       self.msg("d", "c", "assistant", "y" * 5000 + " LAST END")])
        t = ea.recent_turns(str(f), budget=10000)
        self.assertEqual(t[0]["text"], long_user.strip())
        self.assertEqual(len(t[1]["text"]), ea.REPLY_CHARS)
        self.assertTrue(t[1]["text"].endswith("OLD END"))
        self.assertEqual(len(t[3]["text"]), ea.LAST_REPLY_CHARS)
        self.assertTrue(t[3]["text"].endswith("LAST END"))

    def test_merges_reply_blocks_and_drops_image_placeholders(self):
        f = self.tmp / "m.jsonl"
        self.write(f, [self.msg("a", None, "user", "fix it"),
                       self.msg("b", "a", "user", "[Image: source: /tmp/x.png]"),
                       self.msg("c", "b", "assistant", "Looking."),
                       self.msg("d", "c", "assistant", "Fixed.")])
        self.assertEqual(ea.recent_turns(str(f)),
                         [{"role": "user", "text": "fix it"},
                          {"role": "assistant", "text": "Looking.\nFixed."}])

    def test_history_stays_within_the_token_budget(self):
        f = self.tmp / "b.jsonl"
        entries, parent = [], None
        for i in range(40):
            role = "user" if i % 2 == 0 else "assistant"
            entries.append(self.msg(str(i), parent, role, "word " * 400))
            parent = str(i)
        self.write(f, entries)
        t = ea.recent_turns(str(f))
        # The latest reply is always kept, on top of the budget.
        self.assertEqual(t[-1]["role"], "assistant")
        self.assertLessEqual(sum(ea.est_tokens(x["text"]) for x in t[:-1]), ea.HISTORY_TOKENS)
        self.assertLessEqual(len(t), 20)

    def test_latest_reply_kept_even_with_no_budget(self):
        f = self.tmp / "z.jsonl"
        self.write(f, [self.msg("a", None, "user", "fix the bug"),
                       self.msg("b", "a", "assistant", "Plan: branch, eval, merge. Go ahead?")])
        self.assertEqual(ea.recent_turns(str(f), budget=0),
                         [{"role": "assistant", "text": "Plan: branch, eval, merge. Go ahead?"}])

    def test_skips_compaction_summary_meta_and_interrupt_markers(self):
        # Regression: a resumed session sent its 19k-char compaction summary as
        # a user message, and Jev lost confidence on a plain go-ahead.
        f = self.tmp / "c.jsonl"
        summary = dict(self.msg("a", None, "user", "This session is being continued ... " * 500),
                       isCompactSummary=True, isVisibleInTranscriptOnly=True)
        meta = dict(self.msg("b", "a", "user", "Output token limit hit. Resume directly."), isMeta=True)
        self.write(f, [summary, meta,
                       self.msg("c", "b", "user", "[Request interrupted by user]\ncontinue the review"),
                       self.msg("d", "c", "assistant", "Found two issues. Fix them?")])
        self.assertEqual(ea.recent_turns(str(f)),
                         [{"role": "user", "text": "continue the review"},
                          {"role": "assistant", "text": "Found two issues. Fix them?"}])

    def test_jev_state_separates_the_previous_reply(self):
        sent = {}
        class R:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return json.dumps({"answers": answers("high")}).encode()
        import urllib.request
        orig = urllib.request.build_opener
        class Opener:
            def open(self, req, timeout=None):
                sent.update(json.loads(req.data))
                return R()
        urllib.request.build_opener = lambda *handlers: Opener()
        try:
            self._ask("k", "ok, do it", [{"role": "user", "text": "fix the bug"},
                                          {"role": "assistant", "text": "Plan: X. Go ahead?"}])
        finally:
            urllib.request.build_opener = orig
        st = sent["state"]
        self.assertEqual(st["previous_reply"], "Plan: X. Go ahead?")
        self.assertEqual(st["earlier_conversation"], [{"role": "user", "text": "fix the bug"}])

    def test_new_message_capped_only_when_huge(self):
        self.assertEqual(ea.cap_tokens("short", 100), "short")
        huge = "a" * 200000
        capped = ea.cap_tokens(huge, ea.PROMPT_TOKENS)
        self.assertLessEqual(ea.est_tokens(capped), ea.PROMPT_TOKENS + 10)
        self.assertIn("[...]", capped)

    def test_waits_for_a_transcript_written_late(self):
        import threading
        f = self.tmp / "late.jsonl"
        threading.Timer(0.4, lambda: self.write(f, [self.msg("a", None, "user", "hi")])).start()
        self.assertEqual(ea.recent_turns(str(f), wait_s=2)[0]["text"], "hi")

    def test_file_order_when_there_are_no_uuids(self):
        f = self.tmp / "old.jsonl"
        self.write(f, [{"type": "user", "message": {"content": "one"}},
                       {"type": "assistant", "message": {"content": [{"type": "text", "text": "two"}]}}])
        self.assertEqual([t["text"] for t in ea.recent_turns(str(f))], ["one", "two"])

    def test_falls_back_to_the_reply_saved_at_stop(self):
        self.stop("low", last_assistant_message="Want me to add it?")
        seen = {}
        def fake(key, prompt, turns):
            seen["turns"] = turns
            return answers("medium")
        ea.ask_jev = fake
        self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s",
                    "prompt": "add it and push", "transcript_path": str(self.tmp / "missing.jsonl")})
        self.assertEqual(seen["turns"], [{"role": "assistant", "text": "Want me to add it?"}])

    def test_stop_saves_the_end_of_a_long_reply(self):
        self.stop("low", last_assistant_message="x" * 5000 + " Go ahead?")
        last = ea.read_json(ea.state_file("turn", "s"))["last"]
        self.assertEqual(len(last), ea.LAST_REPLY_CHARS)
        self.assertTrue(last.endswith("Go ahead?"))

    def test_wait_depends_on_how_the_session_started(self):
        for source, expected in (("startup", 0), ("clear", 0), ("fork", 6.0), ("resume", 2.0), (None, 2.0)):
            if source:
                self.event({"hook_event_name": "SessionStart", "session_id": "w", "source": source})
            else:
                ea.state_file("session", "w").unlink(missing_ok=True)
            self.assertEqual(ea.transcript_wait("w"), expected, source)

    def test_fresh_session_does_not_wait_for_a_transcript(self):
        self.event({"hook_event_name": "SessionStart", "session_id": "s", "source": "startup"})
        ea.ask_jev = lambda *a: answers("low")
        t = time.time()
        self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s",
                    "prompt": "what is this repo", "transcript_path": str(self.tmp / "none.jsonl")})
        self.assertLess(time.time() - t, 0.5)


class FirstMessageCheck(Base):
    def setUp(self):
        super().setUp()
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"

    def test_first_message_asks_claude_to_check_the_live_level(self):
        out = self.prompt("low", 0.96)
        self.assertIn("Claude will check your level", out["systemMessage"])
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("echo $CLAUDE_EFFORT", ctx)
        self.assertIn("don't mention this check", ctx)

    def test_next_message_is_not_compared_after_claude_asked(self):
        self.prompt("low", 0.96)
        self.stop("max", last_assistant_message="This is a quick question and you're on max. Switch to low?")
        self.assertIn("fits this", self.line("low", text="what is 2+2"))

    def test_next_message_is_compared_when_claude_just_answered(self):
        self.prompt("low", 0.96)
        self.stop("max", last_assistant_message="Paris is the capital of France, known for " + "x" * 700)
        self.assertIn("low is enough", self.line("low", text="what is 2+2"))

    def test_no_check_without_ask_first(self):
        del os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"]
        self.assertNotIn("hookSpecificOutput", self.prompt("low", 0.96))

    def test_no_check_when_unsure(self):
        self.assertNotIn("hookSpecificOutput", self.prompt("high", 0.5))

    def test_heavy_work_after_an_interrupted_tip_is_checked(self):
        # The user pressed Esc after a tip and may have switched: for high or
        # max work Claude reads the live level; for light work it doesn't matter.
        self.stop("low")
        self.prompt("high")                                        # asks (up)
        out = self.prompt("high", text="fix the pagination bug")  # Esc'd, resent
        self.assertIn("echo $CLAUDE_EFFORT", out["hookSpecificOutput"]["additionalContext"])
        self.assertIn("Claude will check your level", out["systemMessage"])

    def test_quiet_still_passes_the_check_to_claude(self):
        os.environ["CLAUDE_PLUGIN_OPTION_QUIET"] = "true"
        out = self.prompt("low", 0.96)
        self.assertNotIn("systemMessage", out)
        self.assertIn("echo $CLAUDE_EFFORT", out["hookSpecificOutput"]["additionalContext"])




class Robustness(Base):
    def test_task_notifications_and_commands_are_skipped(self):
        # Regression: background-task notifications were judged like typed
        # messages (99 of 521 lines in a week) and set off effort questions.
        ea.ask_jev = lambda *a: (_ for _ in ()).throw(AssertionError("no Jev call"))
        for text in ("<task-notification>\n<task-id>a1</task-id>\n</task-notification>",
                     "<local-command-stdout>Compacted</local-command-stdout>",
                     "/effort high", "/spending-effort-with-jev:high continue"):
            self.assertIsNone(self.event({"hook_event_name": "UserPromptSubmit",
                                          "session_id": "s", "prompt": text}), text)

    def test_message_starting_with_a_path_is_judged(self):
        # Regression: "/Users/me/app.py crashes …" was skipped as a slash command.
        self.assertTrue(ea.typed("/Users/me/app/server.py crashes on start"))
        self.assertIn("fits this", self.line("high", text="/Users/me/app/server.py crashes on start"))

    def test_quiet_go_ahead_prints_nothing(self):
        os.environ["CLAUDE_PLUGIN_OPTION_QUIET"] = "true"
        self.assertIsNone(self.event({"hook_event_name": "UserPromptSubmit",
                                      "session_id": "s", "prompt": "continue"}))

    def test_switch_share_counts_unclear(self):
        # Regression: high 0.40 with unclear 0.45 was shown as "needs high (0.73)".
        kind, _, share = ea.verdict(split(high=0.40, unclear=0.45, low=0.15), "low")
        self.assertEqual(kind, "unsure")
        self.assertLessEqual(share, 0.45)

    def test_first_message_share_is_consistent(self):
        # Regression: less certain answers could say "fits" while more certain
        # ones said "not sure", depending on whether "unclear" was the top pick.
        a = ea.verdict(split(high=0.60, unclear=0.30, low=0.10), None)
        b = ea.verdict(split(high=0.40, unclear=0.45, low=0.15), None)
        self.assertGreater(a[2], b[2])
        self.assertNotEqual((a[0], b[0]), ("unsure", "fits"))

    def test_malformed_jev_answer_gives_the_error_line(self):
        # Regression: an unexpected shape failed silently and left stale advice.
        for bad in ({"effort": {"choice": "high"}},
                    {"effort": {"choice": "huge", "confidence": 0.9}, "handoff_ambiguous": {"noul": 0}},
                    {"effort": {"choice": "high", "confidence": None, "probabilities": ["x"]},
                     "handoff_ambiguous": {"noul": 0}},
                    {"effort": {"choice": "high", "confidence": 0.9}, "handoff_ambiguous": {"noul": None}},
                    # would have shown "maybe low (0.25)" for a "high" answer
                    {"effort": {"choice": "high", "confidence": None}, "handoff_ambiguous": {"noul": 0}}):
            with self.assertRaises(Exception):
                ea.checked(bad)
        def bad_jev(*a):
            return ea.checked({"effort": {"choice": "high"}})
        ea.ask_jev = bad_jev
        out = self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "fix it"})
        self.assertIn("didn't answer", out["systemMessage"])
        self.assertEqual(ea.read_json(ea.state_file("advice", "s"))["kind"], "error")

    def test_total_time_limit(self):
        # Regression: urllib's timeout is per socket operation, so a slow
        # response could outlast the 15 s hook limit.
        start = time.time()
        with self.assertRaises(TimeoutError):
            ea.within(0.3, lambda: time.sleep(2))
        self.assertLess(time.time() - start, 1.0)
        self.assertEqual(ea.within(1, lambda: 42), 42)
        with self.assertRaises(KeyError):
            ea.within(1, lambda: {}["x"])

    def test_redirects_are_refused_so_the_key_stays_put(self):
        # Regression: urllib re-sent the Authorization header to wherever a
        # redirect pointed.
        import http.server
        import threading
        got = {}

        class Other(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                got["auth"] = self.headers.get("Authorization")
                self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
            do_POST = do_GET
            def log_message(self, *a): pass

        other = http.server.HTTPServer(("127.0.0.1", 0), Other)

        class Api(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{other.server_port}/steal")
                self.end_headers()
            def log_message(self, *a): pass

        api = http.server.HTTPServer(("127.0.0.1", 0), Api)
        for server in (api, other):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        orig = ea.JEV_URL
        ea.JEV_URL = f"http://127.0.0.1:{api.server_port}/v1"
        try:
            with self.assertRaises(Exception):
                self._ask("secret-key", "fix the bug", [])
        finally:
            ea.JEV_URL = orig
            api.shutdown(); other.shutdown()
        self.assertNotIn("auth", got)

    def test_bad_bytes_and_odd_lines_keep_the_history(self):
        # Regression: one invalid byte, a JSON list line or a text block with
        # "text": null made the hook lose all history (or show the wrong error).
        f = self.tmp / "odd.jsonl"
        good = [{"uuid": "a", "parentUuid": None, "type": "user", "message": {"content": "fix the bug"}},
                {"uuid": "b", "parentUuid": "a", "type": "assistant",
                 "message": {"content": [{"type": "text", "text": None}, {"type": "text", "text": "Found it."}]}}]
        raw = (b"[1, 2]\n" + b"\xff\xfe broken\n" + b'{"message": "string"}\n'
               + b"".join(json.dumps(e).encode() + b"\n" for e in good) + b'{"uuid": "c", "type": "us\xc3')
        f.write_bytes(raw)
        start = time.time()
        turns = ea.recent_turns(str(f), wait_s=2)
        self.assertLess(time.time() - start, 1.0)
        self.assertEqual([t["text"] for t in turns], ["fix the bug", "Found it."])

    def test_reminder_block_does_not_hide_what_the_user_typed(self):
        entry = {"type": "user", "message": {"content": [
            {"type": "text", "text": "<system-reminder>Today is Monday.</system-reminder>"},
            {"type": "text", "text": "why does the build fail?"}]}}
        self.assertEqual(ea._text(entry), "why does the build fail?")
        pasted = {"type": "user", "message": {"content": "<pasted_content id=\"1\">log lines</pasted_content>"}}
        self.assertIn("log lines", ea._text(pasted))
        note = {"type": "user", "message": {"content": "<task-notification>done</task-notification>"}}
        self.assertEqual(ea._text(note), "")

    def test_accepted_switch_is_not_remembered_as_a_decline(self):
        # Review regression: the stay record was written when a tip was shown
        # and never cleared, so after the user accepted a switch and later came
        # back to that level, Claude stopped asking in that direction.
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.stop("low")
        self.prompt("high")                                    # ⬆ from low
        self.stop("low", last_assistant_message="Needs high; switch first?")
        self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "continue"})
        self.stop("high", last_assistant_message="Done. " * 200)  # the user switched
        self.prompt("low", text="what does this flag do?")    # ⬇ from high
        self.stop("high", last_assistant_message="Low is enough; switch?")
        self.event({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "continue"})
        self.stop("low", last_assistant_message="It toggles caching. " * 50)  # switched down
        out = self.prompt("high", text="now find the race in the scheduler")
        self.assertIn("echo $CLAUDE_EFFORT", out["hookSpecificOutput"]["additionalContext"])

    def test_fit_line_never_names_a_level_that_needs_a_switch(self):
        # Review regression: with "unclear" counted toward staying, the ✓ line
        # named Jev's top level even when that level was a switch away.
        for probs in ({"low": 0.25, "high": 0.30, "unclear": 0.45},
                      {"low": 0.26, "max": 0.28, "unclear": 0.46}):
            kind, level, _ = ea.verdict(answers("high", 0.3, probs=probs), "low")
            self.assertEqual((kind, level), ("match", "low"), probs)
        self.assertEqual(ea.verdict(answers("high", 0.3, probs={"high": 0.4, "max": 0.35, "unclear": 0.25}),
                                    "xhigh")[1], "high")

    def test_short_reply_after_an_off_level_counts_as_the_question(self):
        # Review regression: Claude asking without a question mark wasn't seen
        # as a question, so the next message was compared with the old level.
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_FIRST"] = "true"
        self.stop("low")
        self.prompt("high")
        self.stop("low", last_assistant_message="This needs high. Switch with /effort high and say continue, or tell me to go ahead as is.")
        self.assertIn("fits this", self.line("high", text="switched, go"))


if __name__ == "__main__":
    unittest.main()
