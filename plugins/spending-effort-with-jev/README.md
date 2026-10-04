# spending-effort-with-jev

Shows which `/effort` level each message needs, the moment you send it, and switches on your OK. TypeSafe's Jev model reads your message and gives a one-line verdict against the level Claude is about to run on (`⬆ needs high`, `⬇ low is enough`, `✓ medium fits`). When the level looks wrong, in either direction, a dialog (`ask_first`) or a band above the prompt (1: switch, 2: keep) switches it for that message's turn. It never switches on its own.

Needs Claude Code 2.1.287 or later and a [TypeSafe](https://typesafe.ai) API key, entered when you enable the plugin and kept in secure storage.

Options: `language` (`en` / `zh`), `quiet`, `ask_first`, `log_decisions`.

Full documentation, screenshots and evaluation: https://github.com/Yaxin9Luo/spending-effort-with-jev
Privacy: https://github.com/Yaxin9Luo/spending-effort-with-jev/blob/main/PRIVACY.md

MIT licensed. Independent project, not affiliated with Anthropic or TypeSafe.
