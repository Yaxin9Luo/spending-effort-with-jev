# Privacy

spending-effort-with-jev is a Claude Code plugin. It has no server of its own and collects nothing for its author.

## What leaves your machine

On each message you type in Claude Code, the plugin makes one HTTPS request to TypeSafe's Jev API (`api.typesafe.ai`), authenticated with the TypeSafe API key you entered. The request contains:

- the message you just typed, in full (a giant paste is cut to about 20k tokens, keeping its start and end);
- Claude's latest reply (its last 3,000 characters) and older conversation, about 1,500 tokens: your messages whole, Claude's older replies trimmed to their last 1,500 characters. Compaction summaries, Claude Code's own notices and skill instructions are not sent.

Slash commands, background-task notices, scheduled prompts, messages from other sessions and bare go-aheads ("ok", "continue") are not judged, so they aren't sent on their own; a scheduled prompt or an earlier "ok" can still be part of the older conversation sent with your next message. Nothing else is sent: no files, no tool output, no environment variables, no other credentials.

Claude Code makes the request for the plugin (a mod has no network of its own) and follows redirects. On a redirect to another host it drops the API key (checked on Claude Code 2.1.288), but the message would go there too; the v0.2 hook refused redirects, which a mod can't. TypeSafe's API isn't known to redirect.

For a go-ahead (a bare "ok" or "continue", or a reply Jev can't place, like "OK, start phase 0"), the plugin also asks Claude Code's small model, on your own Claude account, to size the work: it gets the go-ahead and up to about 6,000 tokens of recent conversation, filtered the same way, with the effort rubric.

How TypeSafe handles that data is covered by TypeSafe's [privacy policy](https://www.typesafe.ai/privacy-policy). It says TypeSafe does not train or fine-tune models on your inputs; it doesn't give a fixed retention period.

## What stays on your machine

- Your API key is kept in Claude Code's secure storage (the plugin's `sensitive` option). The plugin reads it only from that option and sends it only to `api.typesafe.ai`.
- No state files. While a session runs, Claude Code holds the plugin's state in memory: Jev's verdict until Claude's next request, the level you switched to, and the switches you turned down. It's gone when the session ends.
- Only if you turn on `log_decisions`: `decisions.jsonl` in `~/.claude/plugins/data/spending-effort-with-jev-spending-effort-with-jev/` gets one line per message, decision, offer and failure, with Jev's probabilities, the plugin's decision, your setting and the level sent, your answer to each offer (switch, keep, other, dismissed), the session id, and lengths (characters, number of context messages). A failure is logged by its kind (a timeout, an HTTP status), never by what the response said. The log never contains the text of your messages or of Claude's replies. It grows to about 1 MB, then the previous file is kept as `decisions.1.jsonl`. Delete either file any time.
- Files the v0.2 hook kept in that folder (`advice-`, `live-`, `session-`, `stay-`, `tip-` and `turn-*.json`, `no-key-notice-shown`, and `bin/`) are no longer used and can be deleted. If you set up the v0.2 status line, remove its `statusLine` setting first: it runs `bin/statusline.py` and keeps writing `live-*.json`.

## Turning it off

Disable or uninstall the plugin under `/plugin`. Nothing is sent while it's disabled.
