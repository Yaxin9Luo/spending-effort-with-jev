// The mod's judgement on the cases tests/test_parity.py sends on stdin, so
// they can be compared with the Python hook the eval measured.
// Run by test_parity.py: bun tests/parity.ts < cases.json
import {
  capTokens,
  checked,
  estTokens,
  isGoAhead,
  isTyped,
  jevBody,
  recentTurns,
  verdict,
} from '../plugins/spending-effort-with-jev/hooks/judge.ts'

const cases = JSON.parse(await Bun.stdin.text())

const out = {
  verdicts: cases.verdicts.map(([answers, current]: [any, string | null]) => {
    const v = verdict(answers, current)
    return [v.kind, v.level, v.share]
  }),
  checked: cases.checked.map((raw: unknown) => {
    try {
      checked(raw)
      return true
    } catch {
      return false
    }
  }),
  prompts: cases.prompts.map((p: string) => [isTyped(p.trim()), isGoAhead(p.trim())]),
  tokens: cases.texts.map((t: string) => [estTokens(t), capTokens(t, 50)]),
  bodies: cases.bodies.map(([prompt, turns]: [string, any[]]) => jevBody(prompt, turns)),
  turns: cases.conversations.map(([rows, budget]: [any[], number]) => recentTurns(rows, budget)),
}

process.stdout.write(JSON.stringify(out))
