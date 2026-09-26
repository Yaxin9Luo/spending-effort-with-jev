# Privacy

spending-effort-with-jev is a Claude Code plugin. It has no server of its own and collects nothing for its author.

## What leaves your machine

On each message you send in Claude Code, the plugin makes one HTTPS request to TypeSafe's Jev API (`api.typesafe.ai`), authenticated with the TypeSafe API key you entered. The request contains:

- the message you just sent, in full;
- recent conversation from the current branch: up to 20 messages, about 8k tokens. Your messages are sent whole; Claude's replies are trimmed to their last 1,500 characters (3,000 for the latest one).

Bare go-aheads ("ok", "continue") and slash commands are not sent. Nothing else is sent: no files, no tool output, no environment variables, no other credentials.

How TypeSafe handles that data is covered by TypeSafe's [privacy policy](https://www.typesafe.ai/privacy-policy). It says TypeSafe does not train or fine-tune models on your inputs; it doesn't give a fixed retention period.

## What stays on your machine

- Your API key is kept in Claude Code's secure storage (the plugin's `sensitive` option). The plugin reads it only from that option.
- Small state files (the last effort level, the last advice, the session's start type) go in the plugin's data directory, `~/.claude/plugins/data/`, and are pruned after 14 days.

## Turning it off

Disable or uninstall the plugin under `/plugin`. Nothing is sent while it's disabled.
