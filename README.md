# spending-effort-with-jev

A Claude Code plugin that tells you when to switch `/effort`. Each time you send a message, [TypeSafe](https://typesafe.ai)'s Jev model reads it (plus the last few turns) and judges how much effort the task deserves. When that differs from your current level, you see one line:

```
Effort tip: `/effort high` (now low, confidence 0.99)
```

It never switches effort for you and never blocks your message. It only suggests.

## Why

Thariq Shihipar's post [Using Claude Code: Spending your effort](https://claude.dev/blog/spending-your-effort/) shows that higher effort mostly buys more self-verification and edge-case testing:

- **Low** for quick back-and-forth while you're watching: questions, brainstorming, sketches, small edits.
- **Medium** for ordinary feature work.
- **High** where verification matters: bug fixes in existing code, testing, data analysis.
- **Max** for hard work Claude does fully on its own.

It also shows that effort fixes missed edge cases but not a wrong approach. So before a long hands-off run, pin down the spec first. This plugin turns that rule of thumb into a per-message check.

This is an independent project. It is not affiliated with or endorsed by Anthropic or TypeSafe.

## What it checks

One Jev request per message with two questions, answered in parallel:

1. **Which effort level fits?** It picks from low, medium, high, max, or *unclear*. The *unclear* option is there for messages like "continue" or "ok" that don't say what the task is. Without it, the model would be forced to guess.
2. **Is this a long hands-off task with ambiguous requirements?** If yes, it suggests having Claude interview you before you switch to max.

It stays silent when:
- the answer is *unclear*
- confidence is below 0.6
- the suggestion is within one level of your current effort (`xhigh` counts as close to both `high` and `max`)
- it would repeat the tip it gave on your previous message

Slash commands are skipped. Errors and timeouts are ignored.

## Install

You need Python 3 and a TypeSafe API key from [typesafe.ai](https://typesafe.ai).

```
/plugin marketplace add Yaxin9Luo/spending-effort-with-jev
/plugin install spending-effort-with-jev@spending-effort-with-jev
```

Claude Code asks for your API key when you enable the plugin and keeps it in your system's secure storage. You can also leave the field empty and export `TYPESAFE_API_KEY` instead. Set `language` to `zh` for Chinese tips.

## Cost, latency, privacy

- **Latency:** one request per message you send. That's about 0.5 s median in our tests, with a 6 s client timeout.
- **Privacy:** your message and up to six recent text turns (each cut to 600 characters) are sent to `api.typesafe.ai`. Don't install this if that's not acceptable for your work.
- **Cost:** billed to your TypeSafe key.

## Tuning

The thresholds are constants at the top of [`effort_advisor.py`](plugins/spending-effort-with-jev/scripts/effort_advisor.py): `CONFIDENCE_MIN` (0.6) and `AMBIGUITY_MIN` (0.7). If the ambiguity tip fires too often, raise `AMBIGUITY_MIN`.

## Tests

```
python3 -m unittest discover tests      # offline, policy logic
TYPESAFE_API_KEY=... python3 tests/eval_live.py   # 14 labelled prompts against the live API
```

The live set is small, and the labels are the author's judgement. Treat it as a smoke test, not a benchmark.

## License

MIT
