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


def answers(choice, conf=0.9, amb=0.0):
    return {"effort": {"type": "choice", "choice": choice, "confidence": conf},
            "handoff_ambiguous": {"type": "noul", "noul": amb}}


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
        self.assertIsNone(ea.suggestion(answers("high", 0.4), "low"))


class Status(unittest.TestCase):
    def kind(self, *args, **kw):
        return ea.status(*args, **kw)[0]

    def test_kinds(self):
        self.assertEqual(self.kind(answers("high"), "low"), "up")
        self.assertEqual(self.kind(answers("low"), "max"), "down")
        self.assertEqual(self.kind(answers("medium"), "medium"), "match")
        self.assertEqual(self.kind(answers("high"), None), "fits")
        self.assertEqual(self.kind(answers("high", 0.5), "low"), "unsure")
        self.assertEqual(self.kind(answers("unclear", 0.99), "low"), "unclear")
        self.assertEqual(self.kind(answers("max", amb=0.9), "low"), "ambiguous")

    def test_up_line_says_what_to_do(self):
        text = ea.status(answers("high", 0.98), "low")[1]
        self.assertIn("needs high", text)
        self.assertIn("was low", text)
        self.assertIn("/effort high", text)

    def test_live_level_worded_as_now(self):
        self.assertIn("now low", ea.status(answers("high"), "low", "live")[1])
        self.assertIn("you're on it", ea.status(answers("high"), "high", "live")[1])

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
                                text = ea.status(answers(rec, conf, amb), cur, src, lg, ask)[1]
                                self.assertNotIn("`", text)
                                self.assertLessEqual(width(text), 76, text)

    def test_chinese(self):
        self.assertIn("需要 high", ea.status(answers("high"), "low", language="zh")[1])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        ea.STATE_DIR = self.tmp
        self._ask, self._key, self._env = ea.ask_jev, ea.api_key, dict(os.environ)
        ea.api_key = lambda: "k"
        for k in list(os.environ):
            if k.startswith("CLAUDE_PLUGIN_OPTION_"):
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
        self.assertIn("same as last turn", self.line("medium"))
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
        self.assertIn("same as last turn", self.line("high"))

    def test_completed_tip_turn_is_compared_normally(self):
        self.stop("low")
        self.line("high")
        self.stop("low")  # the user let it run
        self.assertIn("was low", self.line("high"))

    def test_ask_mode(self):
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_BEFORE_UPGRADE"] = "true"
        self.stop("low")
        out = self.prompt("high")
        self.assertIn("check with you", out["systemMessage"])
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("/effort high", ctx)
        self.assertIn("wait", ctx)
        self.stop("low")  # Claude asked and stopped
        # The user may have switched since, so the next message isn't compared.
        self.assertIn("fits this", self.line("high", text="switched, go"))
        self.stop("high")
        self.assertIn("same as last turn", self.line("high"))

    def test_ask_turn_interrupted_does_not_suppress_twice(self):
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_BEFORE_UPGRADE"] = "true"
        self.stop("low")
        self.prompt("high")          # Claude would ask...
        self.line("high")            # ...but the user hit Esc and resent
        self.stop("high")
        self.assertIn("same as last turn", self.line("high"))

    def test_ask_mode_leaves_downgrades_alone(self):
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_BEFORE_UPGRADE"] = "true"
        self.stop("max")
        self.assertNotIn("hookSpecificOutput", self.prompt("low"))

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
            self.assertIn("nothing to judge", out["systemMessage"], text)

    def test_repeated_tip_is_short_after_the_user_stayed(self):
        self.stop("low")
        self.assertIn("Esc", self.line("high"))
        self.stop("low")  # let it run on low
        again = self.line("high")
        self.assertIn("needs high", again)
        self.assertIn("was low", again)
        self.assertNotIn("Esc", again)
        self.stop("low")
        self.assertIn("/effort max", self.line("max"))  # a different tip is spelled out

    def test_ask_mode_asks_once_per_situation(self):
        os.environ["CLAUDE_PLUGIN_OPTION_ASK_BEFORE_UPGRADE"] = "true"
        self.stop("low")
        self.assertIn("hookSpecificOutput", self.prompt("high"))
        self.stop("low")                            # Claude asked
        self.prompt("high", text="go ahead as is")  # not compared (after the ask)
        self.stop("low")                            # ran on low, the user's choice
        out = self.prompt("high")
        self.assertNotIn("hookSpecificOutput", out)
        self.assertIn("was low", out["systemMessage"])

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


if __name__ == "__main__":
    unittest.main()
