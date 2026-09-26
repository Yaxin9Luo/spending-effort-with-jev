"""Offline tests for the suggestion policy. Run: python3 -m unittest discover tests"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "plugins" / "spending-effort-with-jev" / "scripts"))
import effort_advisor as ea  # noqa: E402


def answers(choice, conf, amb=0.0):
    return {"effort": {"type": "choice", "choice": choice, "confidence": conf},
            "handoff_ambiguous": {"type": "noul", "noul": amb}}


class Decide(unittest.TestCase):
    def test_suggests_when_levels_differ(self):
        self.assertIn("/effort high", ea.decide(answers("high", 0.9), "low"))

    def test_silent_when_same_level(self):
        self.assertIsNone(ea.decide(answers("medium", 0.9), "medium"))

    def test_xhigh_counts_as_close_to_high_and_max(self):
        self.assertIsNone(ea.decide(answers("high", 0.9), "xhigh"))
        self.assertIsNone(ea.decide(answers("max", 0.9), "xhigh"))

    def test_silent_when_unclear(self):
        self.assertIsNone(ea.decide(answers("unclear", 0.99), "low"))

    def test_silent_when_low_confidence(self):
        self.assertIsNone(ea.decide(answers("high", 0.4), "low"))

    def test_ambiguous_handoff_wins(self):
        msg = ea.decide(answers("max", 0.9, amb=0.8), "low")
        self.assertIn("interview", msg)

    def test_unknown_current_level_still_suggests(self):
        self.assertIn("/effort low", ea.decide(answers("low", 0.9), "unknown"))

    def test_suggestion_ignores_confidence_for_dedup(self):
        # Same advice at different confidence must compare equal, so it isn't repeated.
        self.assertEqual(ea.suggestion(answers("high", 0.94), "low"),
                         ea.suggestion(answers("high", 0.93), "low"))

    def test_chinese(self):
        self.assertIn("effort 建议", ea.decide(answers("high", 0.9), "low", "zh"))


class Flow(unittest.TestCase):
    """Prompt -> first tool call / stop, with Jev stubbed out."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        ea.STATE_DIR = Path(self.tmp)
        self._ask, self._key = ea.ask_jev, ea.api_key
        ea.api_key = lambda: "k"

    def tearDown(self):
        ea.ask_jev, ea.api_key = self._ask, self._key

    def run_event(self, data):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            if data["hook_event_name"] == "UserPromptSubmit":
                ea.on_prompt(data)
            else:
                ea.on_turn_event(data, data["hook_event_name"])
        return json.loads(buf.getvalue()) if buf.getvalue() else None

    def prompt(self, choice, conf=0.9, amb=0.0, sid="s"):
        ea.ask_jev = lambda *a: answers(choice, conf, amb)
        return self.run_event({"hook_event_name": "UserPromptSubmit",
                               "session_id": sid, "prompt": "do the thing"})

    def tool(self, level, sid="s"):
        return self.run_event({"hook_event_name": "PreToolUse", "session_id": sid,
                               "effort": {"level": level}})

    def stop(self, level, sid="s"):
        return self.run_event({"hook_event_name": "Stop", "session_id": sid,
                               "effort": {"level": level}})

    def test_prompt_itself_prints_nothing(self):
        self.assertIsNone(self.prompt("high"))

    def test_first_tool_call_tells_agent_and_user(self):
        self.prompt("high")
        out = self.tool("low")
        self.assertIn("/effort high", out["systemMessage"])
        self.assertIn("`low`", out["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(self.tool("low"))       # only once per turn
        self.assertIsNone(self.stop("low"))

    def test_uses_real_current_level(self):
        self.prompt("high")
        self.assertIsNone(self.tool("high"))

    def test_stop_covers_turns_without_tools(self):
        self.prompt("low")
        out = self.stop("high")
        self.assertIn("/effort low", out["systemMessage"])
        self.assertNotIn("hookSpecificOutput", out)

    def test_same_tip_not_repeated_next_turn(self):
        self.prompt("high")
        self.assertIsNotNone(self.tool("low"))
        self.prompt("high", conf=0.8)
        self.assertIsNone(self.tool("low"))

    def test_slash_command_clears_pending(self):
        self.prompt("high")
        self.run_event({"hook_event_name": "UserPromptSubmit", "session_id": "s",
                        "prompt": "/effort high"})
        self.assertIsNone(self.tool("low"))

    def test_ambiguous_handoff_asks_agent_to_offer_interview(self):
        self.prompt("max", amb=0.9)
        out = self.tool("medium")
        self.assertIn("ambiguous", out["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
