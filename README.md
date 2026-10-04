# spending-effort-with-jev

**Know which `/effort` level each message needs, and switch with one key.** A Claude Code plugin: every message you type is read by [TypeSafe](https://typesafe.ai)'s Jev model, which judges how much effort the task deserves. Before Claude starts, you get a one-line verdict against the level Claude is about to run on, and when that level looks wrong, one key switches it.

- **With `ask_first` on**, a dialog asks before Claude starts. On `low` for a tricky bug: "This looks like high-effort work, and the session is on low. Switch to high for it?" On `max` for a quick question, it offers to drop to `low`.
- **With it off**, nothing waits on you: while Claude works, a band above the prompt offers `1: Switch to high  2: Keep low  0: Close`, and a switch applies from Claude's next step. The offer goes when the turn ends.

It switches only when you say so. Needs Claude Code 2.1.287 or later: v0.3 is written as a mod (a TypeScript hooks module), which is what lets it see your live level and switch it.

**Upgrading from v0.2:** if you set up its status line (a `statusLine` setting running `bin/statusline.py`), remove that setting; v0.3 shows its line itself.

**Also in this marketplace: [elizabeth-progress](plugins/elizabeth-progress)**, a context-window progress bar above the prompt with Elizabeth from *Gintama* walking on it, plus turns left to auto-compact and your rate limits. It's a separate plugin with no key: install either or both (`/plugin install elizabeth-progress@spending-effort-with-jev`). Both share the band above the prompt.

## Install

**Easiest: let Claude Code install it.** Paste this into Claude Code:

```
Install the Claude Code plugin from https://github.com/Yaxin9Luo/spending-effort-with-jev.
Read its README first. Then:
1. Run: claude plugin marketplace add Yaxin9Luo/spending-effort-with-jev
2. Run: claude plugin install spending-effort-with-jev@spending-effort-with-jev
3. The plugin needs a TypeSafe API key (https://typesafe.ai); nothing else to install.
   Tell me to enter the key under /plugin (it goes to secure storage, not this chat).
4. Ask me whether to turn on ask_first (a dialog asks before Claude starts when the
   effort level looks wrong). If yes, run:
   claude plugin install spending-effort-with-jev@spending-effort-with-jev --config ask_first=true
5. Tell me to run /reload-plugins, then send a test message.
```

**Or by hand** (Claude Code 2.1.287 or later and a [TypeSafe](https://typesafe.ai) API key needed):

```
/plugin marketplace add Yaxin9Luo/spending-effort-with-jev
/plugin install spending-effort-with-jev@spending-effort-with-jev
```

Paste your key when Claude Code asks; it's kept in secure storage, and the plugin reads the key from nowhere else. Then `/reload-plugins`. Jev itself is a hosted API, so there's nothing else to install.

## What the lines mean

The line shows in Claude Code's status area as soon as Claude's first request is about to go out, and above the prompt a small gauge shows it too: four pixel bars, low to max, the level Claude runs on solid and the one Jev names blinking (block bars in the terminal). On a model without effort levels, or with a token budget instead of a level, there's nothing to compare, so no line shows (the message is still sent to Jev).

| Line | Meaning |
|---|---|
| `⬆ effort: needs high (0.99) · now low` | Needs more effort than the level this message would run on. With `ask_first`, the dialog asks; otherwise the band above the prompt offers the switch. |
| `⬇ effort: low is enough (0.95) · now max` | You're spending more than this needs. Same offer, downward. |
| `✓ effort: medium fits this (0.91) · now medium` | Your level suits this message. |
| `○ effort: maybe high (0.55), not sure · keep your level` | Jev's vote is split between staying and switching, so no advice. |
| `○ effort: nothing to judge here · keep your level` | Jev found no task in the message (say, "run it" as your first message) and there's no conversation to size it from. |
| `○ effort: go-ahead · keep your level` | A go-ahead ("ok", "continue") whose work couldn't be sized (see [How it works](#how-it-works)). |
| `⬆ effort: high · you chose low` | You kept your level when this same message was offered a switch; it isn't asked twice. |
| `▶ high (bar says low) · …` | You switched here: Claude's requests go out on `high` while the setting under the input box stays `low`. Every line starts with it while that lasts. |
| `⚠ effort: long run, fuzzy spec → have Claude interview you, then go max` | A long hands-off task with open questions (also a toast). More effort won't fix a wrong reading of the task; a few questions first will. |

**"now low"** is the level Claude's request is about to run on: your setting, or the level you switched to here. The mod reads it from the request itself, so a switch you made a moment ago is never missed.

The number is how much of Jev's whole answer backs the line: for a switch, the share on levels one or more steps away in that direction; for "fits", the share on your level (for xhigh, on high or max) plus "unclear", which gives no reason to switch. A go-ahead sized from the conversation has no vote behind it, so its line says `(go-ahead)` instead.

## Switching

- **A switch holds for that message's turn only.** Claude Code has no way for a plugin to change your effort setting, so the mod rewrites the level on the requests of that turn instead. The effort control under the input box keeps showing your setting; the status line starts with `▶ high (bar says low)` while the mod is rewriting, and says `back on your setting` when the turn ends. Your next message is judged against the setting again, so what the control shows is what runs unless you just said otherwise.
- **Your own setting wins.** Run `/effort` or pick a different level under the input box, and the mod stops rewriting from the next request.
- **Keep** answers that message only. Each message is its own task, so the next one is judged and asked afresh; only the same message sent again isn't asked again (a go-ahead like "continue" always is: its work changes each time). Closing the band or dismissing the dialog changes nothing and remembers nothing.
- With the band, the switch can't touch the request already running; it applies from Claude's next one. With `ask_first`, the dialog comes before the first request, so the whole turn runs on the level you pick.

## Around the switch

- **The band shows more than the verdict.** Beside the gauge and Jev's line: what Jev's API cost today (from the token usage each Jev answer reports, at TypeSafe's list price: $0.042 per million input tokens, output free) and the levels subagents got, as room allows. Claude's own spending isn't shown: that's not this plugin's to count.
- **Ledger.** The band's Ledger button (or `/effort-ledger`) opens a pane: Jev's API cost and number of calls today and over the last 7 days, the turns that ran on each level, and on how many of the turns Jev judged you ran its level.
- **Subagents get their own level.** When Claude starts a subagent, Jev sizes its task: a lookup runs on low, a careful check on high (never max, which is yours to choose). The main conversation stays on your level.
- **A mid-turn hint.** Once in a long high or max turn, the mod asks Jev whether what's left is mechanical (applying a decided change, running tests, writing the commit). If so, the band offers low for the rest of that turn only.
- **An interview before long fuzzy runs.** When a message hands Claude a long run with important things left open, two or three questions come first (drafted by the small model from your message); your answers go to Claude with it. "Up to Claude" skips a question, "Start now" the rest.
- **Thresholds that learn from you.** After ten answers in one direction, switches you keep taking need a little less of Jev's vote and ones you keep turning down a little more (between 0.6 and 0.85, each direction on its own).

## Options

Set them when you enable the plugin, or later under `/plugin`.

| Option | Default | What it does |
|---|---|---|
| `language` | `en` | `zh` for Chinese lines. |
| `quiet` | off | Only show a line when a switch is suggested or in effect, a hand-off needs a spec, or the key is rejected. |
| `ask_first` | off | When a message needs a different level (up or down), a dialog asks before Claude starts. Off: the band above the prompt offers the switch without holding Claude up. |
| `subagents` | on | Size each subagent's task with Jev and run it on that level (at most high). |
| `midturn` | on | Offer low for the rest of a long high or max turn when what's left is mechanical. |
| `interview` | on | Ask two or three questions before a long run with open requirements. |
| `self_tune` | on | Move the switch thresholds with your answers, between 0.6 and 0.85. |
| `log_decisions` | off | Keep a local log of Jev's probabilities and each decision (numbers only, never message text) in `~/.claude/plugins/data/spending-effort-with-jev-spending-effort-with-jev/decisions.jsonl`, to tune the thresholds on real use. See [PRIVACY.md](PRIVACY.md). |

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

On the held-out half, with the session on `medium` (Opus 5.5's default) and the current decision rule (v0.2.7):

- **90%** of the switch tips named the right level (43 of 48), and 98% pointed the right way.
- They caught **67%** of the messages that deserved a different level (43 of 64). When Jev's answer is split, the line says so instead of advising.
- Averaged over the four starting levels, 11% of lines were "not sure".
- The "fuzzy spec" warning caught 29 of 33 genuinely ambiguous hand-offs, and fired wrongly on 6 of 187 clear ones (all 220 messages; not a held-out figure).

These use Jev answers recorded with the v0.2.5 wording of the levels; v0.2.6's added wording for non-coding work isn't reflected. The v0.2.5 rule on the same answers gave 95% and 63%. The evaluation ran on the v0.2 Python hook; the v0.3 mod keeps its rule, request and context, and [`tests/test_parity.py`](tests/test_parity.py) checks the two agree on 5,000 random answers and 400 random conversations.

**On real conversations** (measured for v0.2.6 on 2026-09-27; the raw data wasn't kept, so this can't be re-run): 90 messages sampled from my own Claude Code sessions, each with its real context, labelled the same way (κ = 0.62: real messages are harder, for annotators too). Averaged over all four current levels:

| | v0.2.5 | v0.2.6 |
|---|---|---|
| "not sure" | 51% | 20% |
| "nothing to judge" | 8% | 4% |
| Switch tips pointing the right way (up or down) | 89% | 91% |
| Switch tips naming the exact level | 78% | 71% |
| Messages needing a switch that got the right tip | 32% | 58% |

On the 160 written messages, "not sure" fell from 30% to 9%, and the right tip was caught for 79% of messages needing a switch instead of 59%; tips pointed the right way 95% of the time (96% before), and named the exact level 84% of the time instead of 90%. The real conversations aren't published, since they're my private sessions. In my own daily use afterwards (v0.2.6, desktop app, Sep 29 to Oct 2), 48% of lines on typed messages were "not sure", far above both evals; v0.2.7 changes how shares are computed, and whether that closes the gap is still open.

This measures agreement with the post's rule of thumb as the annotators applied it, not whether a level is objectively optimal; the rule's thresholds were picked on the same data. The written set is in [`eval/`](eval).

## How it works

1. **You send a message.** Before it reaches Claude, the mod asks Jev (about 1 s, 6 s timeout) for a level (low / medium / high / max, or *unclear*) and whether it's an ambiguous hand-off. Jev sees your message, Claude's latest reply (what you're answering) and about 1,500 tokens of older conversation. Compaction summaries, Claude Code's own notices and skill instructions, and interrupt markers are left out: nobody wrote them, and long unrelated context makes Jev less sure. Only what you type is judged: slash commands, background-task notices, scheduled prompts and messages from other sessions are not.
2. **Go-aheads are sized from the conversation.** "continue", "ok" or "OK, start phase 0" carry no task Jev can see: the work they start was planned earlier. For those, Claude Code's small model reads the last ~6,000 tokens of conversation against the same rubric and picks the level.
3. **Claude's first request decides.** The mod compares the verdict with the level that request is about to run on, your live level, then asks, offers the switch, or shows the fit.
4. **The verdict uses Jev's whole distribution**, not just its top pick. A switch needs at least 70% of Jev's answer on levels one or more steps away in one direction; "fits" needs at least 70% on your level plus "unclear". So low 0.5 / unclear 0.3 while you're on low is a fit, not "not sure". xhigh counts as close to both high and max.
5. **Once you've kept your level, it stops asking** in that direction from that level, as above.

## Privacy and cost

- **Privacy:** each message you type goes to `api.typesafe.ai` in full (a giant paste is cut to about 20k tokens), with Claude's latest reply (its last 3,000 characters) and older conversation, about 1,500 tokens: your messages whole, Claude's older replies trimmed to their last 1,500 characters. To size a go-ahead, the last ~6,000 tokens of conversation also go to Claude Code's small model, on your own Claude account; a bare "ok" or "continue" goes only there. Don't install the plugin if that's not OK for your work. Details in [PRIVACY.md](PRIVACY.md).
- **Cost:** Jev is cheap. The 220-message evaluation above cost a few cents. Sizing a go-ahead is one small-model call on your Claude plan.
- **Speed:** your message waits for Jev (about 1 s). If Jev doesn't answer in 6 s, you get "no tip this time" and the message goes through; sizing a go-ahead waits up to 6 s more. Nothing else is waited on.

## Development

```
claude plugin test plugins/spending-effort-with-jev       # the mod's tests, UI on terminal and desktop
claude plugin validate plugins/spending-effort-with-jev
python3 -m unittest discover tests        # the v0.2 hook's tests, and parity with the mod (needs bun)
TYPESAFE_API_KEY=... python3 tests/eval_live.py   # dev only; the plugin itself reads the key from its config
claude plugin test plugins/elizabeth-progress           # the progress bar's tests
claude plugin validate plugins/elizabeth-progress
```

The mod is [`plugins/spending-effort-with-jev/hooks/`](plugins/spending-effort-with-jev/hooks): `judge.ts` holds the judgement (what Jev is asked, the verdict, the wording), `register.tsx` the hooks. [`python/`](python) holds the v0.2 Python hook the evaluation ran on. [`bench/`](bench) holds the task harness used for the runs above: headless `claude -p` in a clean environment, graded by hidden tests.

## Status and roadmap

I use this plugin heavily every day, and it has held up well, which is why I'm sharing it. Because it's part of my own daily workflow, I fix problems as soon as I hit them, and I keep adding features when I find better ways to use it.

- **Codex:** a Codex version is planned. It will ship once I've confirmed that switching effort there doesn't drop context or hurt performance.
- **Ideas welcome:** if you have an idea for a feature, or something that would make it more useful, [open an issue](https://github.com/Yaxin9Luo/spending-effort-with-jev/issues) or send a PR. Contributions, including the Codex port, are very welcome.

## Acknowledgements

- **[Thariq Shihipar](https://claude.dev/blog/spending-your-effort/)**, for the post this plugin is built on and for sharing the interview → low → high workflow.
- **[TypeSafe](https://typesafe.ai)**, for Jev. A fast, calibrated judgment model is what makes a check on every message cheap enough to leave on.

This is an independent project, not affiliated with or endorsed by Anthropic or TypeSafe.

## License

MIT. The elizabeth-progress plugin's MIT license covers its code and drawing, not the character; see [its README](plugins/elizabeth-progress#about-the-character).
