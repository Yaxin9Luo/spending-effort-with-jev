#!/usr/bin/env python3
"""Optional status line: the live effort level and Jev's advice for the last message.

Claude Code gives status lines the live effort level (hooks only see it at the
end of a turn), so this also records it for the send-time notice to compare
against. The plugin copies this file to
~/.claude/plugins/data/<plugin id>/bin/ on session start; point the
statusLine setting there so the path survives plugin updates. `/effort` isn't
a status-line refresh trigger, so set refreshInterval (e.g. 3) to pick up a
switch before the next reply.

Prints e.g. "effort low · Jev: high ⬆", "effort medium ✓" or "effort high".
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Running from the bin/ copy inside the plugin's data dir: state lives one up.
if HERE.name == "bin" and "CLAUDE_PLUGIN_DATA" not in os.environ:
    os.environ["CLAUDE_PLUGIN_DATA"] = str(HERE.parent)
sys.path.insert(0, str(HERE))
import effort_advisor as ea  # noqa: E402


def segment(level, advice):
    if not level:
        return ""
    if not advice:
        return f"effort {level}"
    kind, rec, conf = advice.get("kind"), advice.get("rec"), advice.get("conf", 0)
    if kind == "ambiguous":
        return f"effort {level} · ⚠ pin down the spec first"
    if kind in ("fits", "match", "up", "down") and rec in ea.RANK and conf >= ea.CONFIDENCE_MIN:
        if abs(ea.RANK[rec] - ea.RANK[level]) < 1:
            return f"effort {level} ✓"
        arrow = "⬆" if ea.RANK[rec] > ea.RANK[level] else "⬇"
        return f"effort {level} · Jev: {rec} {arrow}"
    return f"effort {level}"


def main():
    data = json.load(sys.stdin)
    session = data.get("session_id")
    level = (data.get("effort") or {}).get("level")
    if level:
        ea.STATE_DIR.mkdir(parents=True, exist_ok=True)
        ea.write_json(ea.state_file("live", session), {"level": level, "t": time.time()})
    print(segment(level, ea.read_json(ea.state_file("advice", session))))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
