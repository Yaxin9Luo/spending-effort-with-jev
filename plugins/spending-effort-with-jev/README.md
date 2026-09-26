# spending-effort-with-jev

Shows which `/effort` level each message needs, the moment you send it. TypeSafe's Jev model reads your message and gives a one-line verdict (`⬆ needs high`, `⬇ low is enough`, `✓ medium fits`) before Claude starts working. With `ask_first` on, Claude asks before starting when the level looks wrong, in either direction. It suggests; it never switches effort for you.

Needs Python 3 and a [TypeSafe](https://typesafe.ai) API key, entered when you enable the plugin and kept in secure storage.

Options: `language` (`en` / `zh`), `quiet`, `ask_first`.

Full documentation, screenshots and evaluation: https://github.com/Yaxin9Luo/spending-effort-with-jev
Privacy: https://github.com/Yaxin9Luo/spending-effort-with-jev/blob/main/PRIVACY.md

MIT licensed. Independent project, not affiliated with Anthropic or TypeSafe.
