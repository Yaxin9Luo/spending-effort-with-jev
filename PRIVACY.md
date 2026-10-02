# Privacy

spending-effort-with-jev is a Claude Code plugin. It has no server of its own and collects nothing for its author.

## What leaves your machine

On each message you send in Claude Code, the plugin makes one HTTPS request to TypeSafe's Jev API (`api.typesafe.ai`), authenticated with the TypeSafe API key you entered. The request contains:

- the message you just typed, in full (a giant paste is cut to about 20k tokens, keeping its start and end);
- Claude's latest reply (its last 3,000 characters) and older conversation from the current branch, about 1,500 tokens: your messages whole, Claude's older replies trimmed to their last 1,500 characters. Compaction summaries and system notices are not sent.

Bare go-aheads ("ok", "continue"), slash commands and background-task notices are not sent. The request goes only to `api.typesafe.ai`: redirects are refused, so the key can't be forwarded elsewhere. Nothing else is sent: no files, no tool output, no environment variables, no other credentials.

How TypeSafe handles that data is covered by TypeSafe's [privacy policy](https://www.typesafe.ai/privacy-policy). It says TypeSafe does not train or fine-tune models on your inputs; it doesn't give a fixed retention period.

## What stays on your machine

- Your API key is kept in Claude Code's secure storage (the plugin's `sensitive` option). The plugin reads it only from that option.
- Small state files go in the plugin's data directory, `~/.claude/plugins/data/` (or `~/.claude/spending-effort-with-jev/` if Claude Code doesn't set one): the level and time of your last turn together with the last 3,000 characters of Claude's last reply (used as context if the transcript isn't readable yet), the last advice, which switches you've already seen, and how the session started. Files untouched for 14 days are deleted when a session starts.
- Only if you turn on `log_decisions`: `decisions.jsonl` in the same folder gets one line per message and per turn, with Jev's probabilities, the plugin's decision, the level each turn ran on, the session id, and lengths (characters, number of context messages). It never contains the text of your messages or of Claude's replies. It grows to 5 MB, then the previous file is kept as `decisions.1.jsonl`. Delete either file any time.

## Turning it off

Disable or uninstall the plugin under `/plugin`. Nothing is sent while it's disabled.
