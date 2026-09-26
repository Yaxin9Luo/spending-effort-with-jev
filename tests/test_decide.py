"""Offline tests for the suggestion policy. Run: python3 -m unittest discover tests"""
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


if __name__ == "__main__":
    unittest.main()
