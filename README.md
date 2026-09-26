# spending-effort-with-jev

**Know which `/effort` level each message needs, the moment you send it.** A Claude Code plugin: every message you send is read by [TypeSafe](https://typesafe.ai)'s Jev model, which judges how much effort the task deserves. You get a one-line verdict before Claude starts working, so you can switch in time.

These lines come from a real session on `low` (they appear as a notice under your message, in the terminal and in the desktop app):

```
> What does list_orders return?
  ○ effort: low fits this (0.99)

> Customers see the same order twice when they page through /orders. Find the root cause and tell me the fix.
  ⬆ effort: needs high (0.99) · was low → Esc, /effort high, continue
```

It suggests; it never switches effort for you and never blocks your message.

## Install

You need Python 3 and a TypeSafe API key ([typesafe.ai](https://typesafe.ai)).

```
/plugin marketplace add Yaxin9Luo/spending-effort-with-jev
/plugin install spending-effort-with-jev@spending-effort-with-jev
```

Paste your key when Claude Code asks, or leave it empty and `export TYPESAFE_API_KEY=...`. Then `/reload-plugins` or start a new session.

## What the lines mean

| Line | Meaning |
|---|---|
| `⬆ effort: needs high (0.99) · was low → Esc, /effort high, continue` | Needs more effort than you have. The first time, it tells you how to switch; if you stay put, later repeats are shorter. |
| `⬇ effort: low is enough (0.95) · was max → /effort low` | You're spending more than this needs. |
| `✓ effort: medium fits (0.91) · same as last turn` | You're on the right level. |
| `○ effort: high fits this (0.98)` | The recommendation, when there's nothing trustworthy to compare with yet (a session's first message, or right after you pressed Esc to switch). |
| `○ effort: maybe high (0.55), not sure · keep your level` | Jev isn't confident, so no advice. |
| `○ effort: nothing to judge here · keep your level` | "ok", "continue" and the like. Answered instantly, without calling Jev. |
| `⚠ effort: long run, fuzzy spec → have Claude interview you, then /effort max` | A long hands-off task with open questions. More effort won't fix a wrong reading of the task; a few questions first will. |

The number is Jev's confidence. **"was low"** is the level your last completed turn ran on: hooks can't see a `/effort` switch until the next turn ends. (The optional status line below fixes that in the terminal.)

## Acting on a tip

- **To apply it to the current message:** stop Claude (Esc in the terminal, the stop button in the desktop app), switch with `/effort high`, then send `continue`. Claude still has your request and picks it up at the new level. This is the same in both clients: once a message is sent, Claude starts at the current level, and a switch applies from the next message. The line says "Esc" in the terminal and "stop" in the desktop app.
- **Or let Claude wait for you:** turn on `ask_before_upgrade`. When a message needs more effort than the session has, Claude asks whether to switch before it does any work, and waits for your answer. It asks once; if you choose to stay, it won't keep asking.
- In the terminal, `/effort <level>` also saves that level as your default for the model. To change just this session, open `/effort` and press `s`.

## Options

Set them when you enable the plugin, or later under `/plugin`.

| Option | Default | What it does |
|---|---|---|
| `language` | `en` | `zh` for Chinese lines. |
| `quiet` | off | Only show a line when a switch is suggested (or a hand-off needs a spec). |
| `ask_before_upgrade` | off | Claude checks with you before starting work that needs more effort than you have. |

## Optional: status line (terminal)

The status line is the one place Claude Code reports your *live* effort level, including right after `/effort`. With it, the bottom of the terminal shows e.g. `effort low · Jev: high ⬆`, then `effort high ✓` once you switch, and the notices compare against your real current level instead of the last turn.

After installing, start one session (the plugin copies the script to a stable path), then add to `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "python3 ~/.claude/plugins/data/spending-effort-with-jev-spending-effort-with-jev/bin/statusline.py",
  "refreshInterval": 3
}
```

`refreshInterval` matters: `/effort` doesn't trigger a status-line refresh by itself. If you already have a status line, call this script from yours and print both. Without the status line, the notices compare against the last completed turn.

## Why effort matters

Thariq Shihipar's post [*Using Claude Code: Spending your effort*](https://claude.dev/blog/spending-your-effort/) is worth reading in full. The short version:

- **Effort buys verification.** Higher effort mostly means Claude reproduces bugs, writes adversarial tests and checks edge cases. On Terminal-Bench 3.0, Fable 5.1's "missed a case" failures fell from 59 to 24 between low and max, while tokens per attempt roughly tripled.
- **It doesn't fix a wrong approach.** Failures from misreading the task didn't go away, so pin down the spec before a long run.
- **The payoff varies by domain.** Hardware (34% → 75%) and security (64% → 87%) gained the most. Rule-following ops work barely moved.
- **His rule of thumb:**
  - **low** for quick back-and-forth, brainstorming and small edits
  - **medium** for everyday feature work
  - **high** when verification or edge cases matter, e.g. a bug in existing code
  - **max** for hard problems Claude should solve fully on its own
- **His loop for new features:** have Claude interview you to fill in the spec → implement on low → iterate on low → verify and test on high.

The catch is remembering to switch. This plugin does the remembering. Its judgment starts from that rule of thumb, adjusted from real use (follow-up questions count as low, bare go-aheads aren't judged at all).

## What the level costs: three real runs

Same task, same model (Opus 5.5), clean environment, graded by hidden tests:

| Task | low | max |
|---|---|---|
| Rename a function across a small codebase | ✅ $0.09 · 14 s | ✅ $0.27 · 72 s |
| Implement an LRU cache with TTL (20 hidden tests) | ✅ $0.10 · 24 s | ✅ $2.47 · 13 min |
| Match npm semver ranges exactly (42 hidden tests) | ✅ $0.35 · 4 min | not run |

On these tasks low was already enough, and max cost up to 25× more and took 30× longer for the same result. Opus 5.5 handled even the edge-case-heavy semver task on low. Effort earns its cost on harder problems: in Anthropic's runs, an HTML sanitizer task went from 1/5 on low to 5/5 on xhigh.

*One run per cell, so these are illustrations rather than a benchmark. The cost is Claude Code's reported API-equivalent cost.*

## How well does Jev judge?

We wrote 160 realistic Claude Code messages (English and Chinese, some with conversation context) and 60 hand-off requests. Three annotators (Opus, Sonnet and Fable, working blind from a rubric based on the post) labelled each one. Agreement was high: Fleiss' κ = 0.82 for level and 0.89 for hand-off ambiguity.

On a held-out test split, with the session on `medium` (Opus 5.5's default):

- **95%** of the switch tips pointed to the right level.
- They caught **63%** of the messages that deserved a different level. When Jev isn't sure, it says so instead of advising.
- The "fuzzy spec" warning caught 29 of 33 genuinely ambiguous hand-offs, and fired wrongly on 6 of 187 clear ones.

This measures agreement with the post's rule of thumb as the annotators applied it, not whether a level is objectively optimal. Everything is in [`eval/`](eval); re-run it with `python3 eval/analyze.py`.

## How it works

1. **You send a message.** Claude Code waits for the hook, which asks Jev (about 0.6 s, 6 s timeout) for a level (low / medium / high / max, or *unclear*) and whether it's an ambiguous hand-off. Jev sees your message plus the last few turns. The line appears before Claude starts.
2. **The turn ends.** The hook records the effort level the turn ran on; that's what the next message is compared with. A typed `/effort` reaches no hook, so right after a tip you acted on (Esc, switch, resend) the plugin doesn't compare, rather than compare with a stale level.
3. **Tips need confidence ≥ 0.7** and a gap of at least one level. xhigh counts as close to both high and max.

Claude Code doesn't let a session raise its own effort, so switching stays with you.

## Privacy and cost

- **Privacy:** each message you send, plus up to six recent text turns (600 characters each), goes to `api.typesafe.ai`. Don't install the plugin if that's not OK for your work.
- **Cost:** Jev is cheap. The 220-message evaluation above cost a few cents.
- **Speed:** besides the Jev call, the hooks cost about 35 ms per message and per turn. Slash commands and go-aheads skip Jev. If the API doesn't answer in 6 s, you get "no tip this time" and your message goes through.

## Development

```
python3 -m unittest discover tests        # offline tests
TYPESAFE_API_KEY=... python3 tests/eval_live.py
```

[`bench/`](bench) holds the task harness used for the runs above: headless `claude -p` in a clean environment, graded by hidden tests.

## Acknowledgements

- **[Thariq Shihipar](https://claude.dev/blog/spending-your-effort/)**, for the post this plugin is built on and for sharing the interview → low → high workflow.
- **[TypeSafe](https://typesafe.ai)**, for Jev. A fast, calibrated judgment model is what makes a check on every message cheap enough to leave on.

This is an independent project, not affiliated with or endorsed by Anthropic or TypeSafe.

## License

MIT
