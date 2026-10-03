// The judgement on its own, ported from tests/test_decide.py (Suggestion,
// Status, Context and Robustness cases that don't need an engine).
import { describe, expect, test } from 'claude-code/testing'

import type { Answers } from '../types'
import {
  EFFORT_CRITERIA,
  LAST_REPLY_CHARS,
  PROMPT_TOKENS,
  REPLY_CHARS,
  VERSION,
  WORDS,
  capTokens,
  checked,
  estTokens,
  isCommand,
  isGoAhead,
  isPersonOrigin,
  isTyped,
  jevBody,
  recentTurns,
  statusLine,
  verdict,
  writtenText,
} from '../hooks/judge'

/** Jev's answer; by default the rest of the probability is spread evenly. */
function answers(choice: string, conf = 0.9, amb = 0, probs?: Record<string, number>): Answers {
  if (!probs) {
    const others = ['low', 'medium', 'high', 'max'].filter(lv => lv !== choice)
    probs = Object.fromEntries(others.map(lv => [lv, Math.round(((1 - conf) / others.length) * 10_000) / 10_000]))
    probs[choice] = conf
  }
  return { effort: { choice, confidence: conf, probabilities: probs }, handoff_ambiguous: { noul: amb } }
}

/** An answer whose top choice is the most probable level. */
function split(probs: Record<string, number>): Answers {
  const top = Object.keys(probs).reduce((a, b) => ((probs[a] ?? 0) >= (probs[b] ?? 0) ? a : b))
  return answers(top, probs[top] ?? 0, 0, probs)
}

describe('verdict', () => {
  test('suggests when levels differ', () => {
    expect(verdict(answers('high'), 'low').kind).toBe('up')
    expect(verdict(answers('high'), 'low').level).toBe('high')
  })

  test('nothing when same level', () => {
    expect(verdict(answers('medium'), 'medium').kind).toBe('match')
  })

  test('xhigh counts as close to high and max', () => {
    expect(verdict(answers('high'), 'xhigh').kind).toBe('match')
    expect(verdict(answers('max'), 'xhigh').kind).toBe('match')
  })

  test('unclear and unsure give no switch', () => {
    expect(verdict(answers('unclear', 0.99), 'low').kind).toBe('unclear')
    expect(verdict(split({ low: 0.45, high: 0.45, medium: 0.1 }), 'low').kind).toBe('unsure')
  })

  test('neighbouring levels splitting the vote is a fit', () => {
    expect(verdict(split({ low: 0.52, unclear: 0.33, high: 0.15 }), 'low').kind).toBe('match')
    expect(verdict(split({ high: 0.5, max: 0.4, medium: 0.1 }), 'xhigh').kind).toBe('match')
    // One level away is a switch, so staying vs. switching split evenly is unsure.
    expect(verdict(split({ medium: 0.45, low: 0.41, high: 0.14 }), 'low').kind).toBe('unsure')
  })

  test('switch needs most of the probability on one side', () => {
    const v = verdict(split({ high: 0.5, max: 0.35, low: 0.15 }), 'low')
    expect(v.kind).toBe('up')
    expect(v.level).toBe('high')
    expect(Math.abs(v.share - 0.85) < 1e-9).toBe(true)
    expect(verdict(split({ high: 0.6, low: 0.4 }), 'low').kind).toBe('unsure')
    expect(verdict(split({ low: 0.9, medium: 0.1 }), 'max').kind).toBe('down')
    expect(verdict(split({ low: 0.9, medium: 0.1 }), 'max').level).toBe('low')
  })

  test('first message (level unknown) uses the top level', () => {
    expect(verdict(split({ high: 0.8, low: 0.2 }), null).kind).toBe('fits')
    expect(verdict(split({ high: 0.5, low: 0.5 }), null).kind).toBe('unsure')
  })

  test('switch share counts unclear', () => {
    // Regression (v0.2.7): high 0.40 with unclear 0.45 was shown as "needs high (0.73)".
    const v = verdict(split({ high: 0.4, unclear: 0.45, low: 0.15 }), 'low')
    expect(v.kind).toBe('unsure')
    expect(v.share <= 0.45).toBe(true)
  })

  test('first-message share is consistent', () => {
    const a = verdict(split({ high: 0.6, unclear: 0.3, low: 0.1 }), null)
    const b = verdict(split({ high: 0.4, unclear: 0.45, low: 0.15 }), null)
    expect(a.share > b.share).toBe(true)
    expect(a.kind === 'unsure' && b.kind === 'fits').toBe(false)
  })

  test('fit line never names a level that needs a switch', () => {
    const splits: Record<string, number>[] = [{ low: 0.25, high: 0.3, unclear: 0.45 }, { low: 0.26, max: 0.28, unclear: 0.46 }]
    for (const probs of splits) {
      const v = verdict(answers('high', 0.3, 0, probs), 'low')
      expect([v.kind, v.level]).toEqual(['match', 'low'])
    }
    expect(verdict(answers('high', 0.3, 0, { high: 0.4, max: 0.35, unclear: 0.25 }), 'xhigh').level).toBe('high')
  })

  test('ambiguity wins', () => {
    expect(verdict(answers('max', 0.9, 0.9), 'low').kind).toBe('ambiguous')
  })

  test('older answers without probabilities spread the rest', () => {
    const v = verdict({ effort: { choice: 'high', confidence: 0.9 }, handoff_ambiguous: { noul: 0 } }, 'low')
    expect(v.kind).toBe('up')
  })
})

describe('lines', () => {
  test('status line per kind', () => {
    // On low, "up" is medium, high and max together: 0.97 + 0.01 + 0.01.
    expect(statusLine('en', verdict(answers('high', 0.97), 'low'), 'low')).toContain('needs high (0.99) · now low')
    expect(statusLine('en', verdict(answers('low', 0.97), 'max'), 'max')).toContain('low is enough')
    expect(statusLine('en', verdict(answers('medium'), 'medium'), 'medium')).toContain('✓ effort: medium fits this')
    expect(statusLine('zh', verdict(answers('high', 0.97), 'low'), 'low')).toContain('需要 high')
  })

  test('no backticks in anything shown', () => {
    for (const l of ['en', 'zh'] as const) {
      const w = WORDS[l]
      const v = verdict(answers('high', 0.97), 'low')
      for (const text of [w.up(v, 'low'), w.question(v, 'low'), w.band({ direction: 'up', level: 'high', from: 'low' }), w.unclear, w.goAhead]) {
        expect(text.includes('`')).toBe(false)
      }
    }
  })
})

describe('what is judged', () => {
  test('go-aheads', () => {
    for (const text of ['ok', 'Continue.', 'go ahead', '继续', '好的！']) expect(isGoAhead(text)).toBe(true)
    expect(isGoAhead('ok, now fix the login bug')).toBe(false)
  })

  test('commands but not paths', () => {
    expect(isCommand('/effort high')).toBe(true)
    expect(isCommand('/spending-effort-with-jev:high continue')).toBe(true)
    expect(isCommand('/修复 bug')).toBe(true) // command names in any script, as the v0.2 hook
    expect(isCommand('/Users/me/app/server.py crashes on start')).toBe(false)
  })

  test('wrappers Claude Code sends as prompts are not typed', () => {
    expect(isTyped('<task-notification><task-id>x</task-id></task-notification>')).toBe(false)
    expect(isTyped('<local-command-stdout>ok</local-command-stdout>')).toBe(false)
    expect(isTyped('')).toBe(false)
    expect(isTyped('<b>bold</b> is not rendering')).toBe(true)
  })

  test('only what a person typed', () => {
    expect(isPersonOrigin({ kind: 'composer' })).toBe(true)
    expect(isPersonOrigin({ kind: 'bridge' })).toBe(true)
    expect(isPersonOrigin(undefined)).toBe(true)
    for (const kind of ['task-notification', 'peer', 'sdk', 'scheduled-trigger', 'plugin', 'unclassified', 'auto-continuation']) {
      expect(isPersonOrigin({ kind })).toBe(false)
    }
  })
})

describe('context', () => {
  test('user messages whole, replies trimmed to their end', () => {
    const longUser = 'please '.repeat(2000).trim()
    const turns = recentTurns(
      [
        { role: 'user', text: longUser },
        { role: 'assistant', text: 'x'.repeat(5000) + ' OLD END' },
        { role: 'user', text: 'ok and then?' },
        { role: 'assistant', text: 'y'.repeat(5000) + ' LAST END' },
      ],
      10_000,
    )
    expect(turns[0]?.text).toBe(longUser)
    expect(turns[1]?.text.length).toBe(REPLY_CHARS)
    expect(turns[1]?.text.endsWith('OLD END')).toBe(true)
    expect(turns[3]?.text.length).toBe(LAST_REPLY_CHARS)
    expect(turns[3]?.text.endsWith('LAST END')).toBe(true)
  })

  test('latest reply kept even with no budget', () => {
    expect(
      recentTurns(
        [
          { role: 'user', text: 'fix the bug' },
          { role: 'assistant', text: 'Plan: branch, eval, merge. Go ahead?' },
        ],
        0,
      ),
    ).toEqual([{ role: 'assistant', text: 'Plan: branch, eval, merge. Go ahead?' }])
  })

  test('history stays within the token budget', () => {
    const rows = Array.from({ length: 40 }, (_, i) => ({ role: i % 2 === 0 ? 'user' : 'assistant', text: 'word '.repeat(400) }))
    const turns = recentTurns(rows)
    expect(turns.at(-1)?.role).toBe('assistant')
    expect(turns.slice(0, -1).reduce((s, t) => s + estTokens(t.text), 0) <= 1500).toBe(true)
  })

  test('tool results, reminders, summaries and markers are not anyone\'s words', () => {
    expect(writtenText({ role: 'user', text: 'x', toolResults: [{}] })).toBe('')
    expect(writtenText({ role: 'user', text: '<system-reminder>Today is Monday.</system-reminder>\nwhy does the build fail?' })).toBe('why does the build fail?')
    expect(writtenText({ role: 'user', text: '<task-notification>done</task-notification>' })).toBe('')
    expect(writtenText({ role: 'user', text: 'This session is being continued from a previous conversation that ran out of context.' })).toBe('')
    expect(writtenText({ role: 'user', text: '[Request interrupted by user]\ncontinue the review' })).toBe('continue the review')
    expect(writtenText({ role: 'user', text: '<pasted_content id="1">log lines</pasted_content>' })).toContain('log lines')
  })

  test('any block Claude Code wraps in a tag, and its notices, are dropped', () => {
    const wrapped = [
      '<local-command-caveat>Caveat: The messages below were generated by the user while running local commands.</local-command-caveat>',
      '<command-name>/shuorenhua</command-name>\n<command-message>shuorenhua</command-message>\n<command-args></command-args>',
      '<bash-input>git status</bash-input>',
      '<ide_opened_file>The user opened the file app.py in the IDE.</ide_opened_file>',
      '<artifact-content-authored-by-others/>',
      'Base directory for this skill: /Users/me/.claude/skills/x\n\n# Skill\nLong instructions...',
      'Another Claude session sent a message: <agent-message>done</agent-message>',
      'Your response above was cut off mid-stream. Resume from where it stopped.',
      '[Image: original 2080x832, displayed at 2000x800. Multiply coordinates by 1.04]',
    ]
    for (const text of wrapped) expect(writtenText({ role: 'user', text })).toBe('')
    expect(writtenText({ role: 'user', text: '<artifact-content-authored-by-others/>\nsummarise the review' })).toBe('summarise the review')
    expect(writtenText({ role: 'user', text: 'why does <b>bold</b> not render?' })).toBe('why does <b>bold</b> not render?')
  })

  test("blocks joined with nothing between them, as the engine's rows are", () => {
    const joined: Array<[string, string]> = [
      ['<system-reminder>\nToday is Monday.\n</system-reminder>fix this', 'fix this'],
      ['fix this<system-reminder>Be brief.</system-reminder>', 'fix this'],
      ['[Request interrupted by user]continue the review', 'continue the review'],
      ['[Image: source: /tmp/shot.png]what is this?', 'what is this?'],
      ['look at this<pasted_content id="1">log</pasted_content>', 'look at this<pasted_content id="1">log</pasted_content>'],
    ]
    for (const [text, words] of joined) expect(writtenText({ role: 'user', text })).toBe(words)
  })

  test("Claude's replies are its own words", () => {
    expect(writtenText({ role: 'assistant', text: 'Base directory for this skill: is a line skills start with.' })).toContain('Base directory')
    expect(writtenText({ role: 'assistant', text: 'Wrap it in <system-reminder>…</system-reminder> tags.' })).toContain('<system-reminder>')
  })

  test('cuts count characters, never half an emoji', () => {
    const reply = 'a' + '😀'.repeat(LAST_REPLY_CHARS)
    const turns = recentTurns([{ role: 'user', text: 'go' }, { role: 'assistant', text: reply }])
    expect([...(turns.at(-1)?.text ?? '')].length).toBe(LAST_REPLY_CHARS)
    expect(JSON.stringify(capTokens('a' + '😀'.repeat(50_000), 100)).includes('\\ud')).toBe(false)
  })

  test('same-role runs merge, newest reply last', () => {
    const turns = recentTurns([
      { role: 'user', text: 'fix it' },
      { role: 'assistant', text: 'Looking.' },
      { role: 'assistant', text: 'Fixed.' },
    ])
    expect(turns).toEqual([
      { role: 'user', text: 'fix it' },
      { role: 'assistant', text: 'Looking.\nFixed.' },
    ])
  })

  test('the previous reply is its own field', () => {
    const body = jevBody('ok, do it', [
      { role: 'user', text: 'fix the bug' },
      { role: 'assistant', text: 'Plan: X. Go ahead?' },
    ]) as { state: { previous_reply: string; earlier_conversation: unknown[] }; questions: { effort: { criteria: unknown } } }
    expect(body.state.previous_reply).toBe('Plan: X. Go ahead?')
    expect(body.state.earlier_conversation).toEqual([{ role: 'user', text: 'fix the bug' }])
    expect(body.questions.effort.criteria).toEqual(EFFORT_CRITERIA)
  })

  test('new message capped only when huge', () => {
    expect(capTokens('short', 100)).toBe('short')
    const capped = capTokens('a'.repeat(200_000), PROMPT_TOKENS)
    expect(estTokens(capped) <= PROMPT_TOKENS + 10).toBe(true)
    expect(capped).toContain('[...]')
  })
})

describe('answers', () => {
  test('malformed answers are refused', () => {
    const bad: unknown[] = [
      { effort: { choice: 'high' } },
      { effort: { choice: 'huge', confidence: 0.9 }, handoff_ambiguous: { noul: 0 } },
      { effort: { choice: 'high', confidence: null, probabilities: ['x'] }, handoff_ambiguous: { noul: 0 } },
      { effort: { choice: 'high', confidence: 0.9 }, handoff_ambiguous: { noul: null } },
      { effort: { choice: 'high', confidence: null }, handoff_ambiguous: { noul: 0 } },
      { effort: { choice: 'toString', confidence: 0.9 }, handoff_ambiguous: { noul: 0 } },
      [],
    ]
    for (const raw of bad) expect(() => checked(raw)).toThrow()
    expect(checked(answers('high')).effort.choice).toBe('high')
  })

  test('version is a release number (kept equal to plugin.json by tests/test_decide.py)', () => {
    expect(/^\d+\.\d+\.\d+$/.test(VERSION)).toBe(true)
  })
})
