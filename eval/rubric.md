# Labelling rubric

Source: Thariq Shihipar, "Using Claude Code: Spending your effort" (claude.dev, 2026-09-25). Effort tells the model how much compute to spend. Higher effort mainly buys more self-verification, edge-case testing and independent judgement. It doesn't fix a wrong approach, and it makes the model decide more things on the user's behalf.

For each message (read with its context), give two labels.

## 1. `level`: the effort the task deserves

- **low**: quick responses while the user is in the loop. Brainstorming, sketching, questions and explanations, easy changes, mechanical or rule-following chores.
- **medium**: most regular software engineering, such as implementing a new feature from a reasonably clear description or a routine refactor. The user will review the result.
- **high**: work where verification matters or there are hidden edge cases. Fixing a bug in an existing codebase, testing or verifying something, performance work, and analysis where setup choices can change the conclusion.
- **max**: the user wants Claude to operate fully autonomously on a difficult problem, e.g. building and verifying a whole app end to end, or finding security vulnerabilities in critical software.
- **unclear**: the message and its context don't reveal what the task is, so no level can be justified. Example: a bare "ok" with no context.

If context makes a short follow-up clear ("looks good, now test it"), label the task it refers to. Pick the single best level. If two are defensible, pick the one the rubric points to most directly.

## 2. `handoff_ambiguous`: true or false

True when the user hands off a long autonomous task (overnight, "finish it all", "don't ask me") and important requirements (goal, scope, success criteria) are left open to interpretation. False otherwise, including hands-off tasks that are already well specified.
