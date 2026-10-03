// The mod end to end through the engine: a typed message is judged at
// prompt.submit, decided at the next main-loop request against the live
// effort, and switched from the UI. Ported from the Flow, FirstMessageCheck
// and Robustness cases of tests/test_decide.py, recast for the mod.
import { describe, expect, mock, test } from 'claude-code/testing'

type World = {
  sent: Array<string | number | undefined>
  asked: string[]
  statuses: Array<string | undefined>
  toasts: string[]
  jevCalls: Array<{ url: string; auth?: string; body: any }>
  files: Record<string, string>
}

type Setup = {
  /** Jev's answer per call, in order; the last repeats. A number answers that HTTP status; `{ raw }` that body. */
  jev?: Array<Record<string, unknown> | number | 'hang'>
  rows?: Array<{ role: string; text: string; toolUses?: unknown[] }>
  classify?: string
  /** Which option to pick in the effort dialog, by its position (0 switch, 1 keep), dismiss it, or type an answer. */
  pick?: number | 'dismiss' | { other: string }
  home?: string
}

/** A Jev answer with most of its weight on `choice`. */
function jev(choice: string, conf = 0.95, amb = 0): Record<string, unknown> {
  const others = ['low', 'medium', 'high', 'max'].filter(lv => lv !== choice)
  const probabilities: Record<string, number> = Object.fromEntries(others.map(lv => [lv, (1 - conf) / others.length]))
  probabilities[choice] = conf
  return { effort: { choice, confidence: conf, probabilities }, handoff_ambiguous: { noul: amb } }
}

/** Stand in for everything beneath the plugin: Jev, the conversation, the dialog, the model loop. */
function world(on: any, setup: Setup): World {
  const w: World = { sent: [], asked: [], statuses: [], toasts: [], jevCalls: [], files: {} }
  const answers = setup.jev ?? [jev('high')]
  let call = 0
  mock.env(on, { HOME: setup.home ?? '/home/test' })
  on('prompt.submit', ($: any, e: any) => ({ text: e.text }))
  on('session.messages', () => ({ value: setup.rows ?? [] }))
  on('session.id', () => ({ value: 'session-1' }))
  on('http.fetch', ($: any, e: any) => {
    const answer = answers[Math.min(call, answers.length - 1)]
    call += 1
    w.jevCalls.push({ url: e.url, auth: e.init?.headers?.Authorization, body: JSON.parse(e.init?.body ?? '{}') })
    if (answer === 'hang') return new Promise(() => undefined)
    if (typeof answer === 'number') return { value: { status: answer, ok: false, headers: {}, text: '' } }
    if (answer && typeof answer.raw === 'string') return { value: { status: 200, ok: true, headers: {}, text: answer.raw } }
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ answers: answer }) } }
  })
  on('model.classify', () => ({ value: setup.classify }))
  on('tool.call', { tool: 'AskUserQuestion' }, ($: any, e: any) => {
    const q = e.questions[0]
    w.asked.push(q.question)
    if (setup.pick === 'dismiss') return { deny: 'dismissed' }
    const answer = typeof setup.pick === 'object' ? setup.pick.other : q.options[setup.pick ?? 0].label
    return { result: { questions: e.questions, answers: { [q.question]: answer } } }
  })
  on('ui.status', ($: any, e: any) => {
    w.statuses.push(e.text)
    return { value: undefined }
  })
  on('ui.toast', ($: any, e: any) => {
    w.toasts.push(e.text)
    return { value: undefined }
  })
  on('fs.read', ($: any, e: any) => (e.path in w.files ? { value: w.files[e.path] } : { deny: 'missing' }))
  on('fs.write', ($: any, e: any) => {
    w.files[e.path] = e.text
    return { value: undefined }
  })
  on('command.run', ($: any, e: any) => ({ text: `ran /${e.command} ${e.args}` }))
  // The engine's own band is nothing; the plugin draws over it.
  on('ui.render', { component: 'AbovePrompt' }, ($: any, e: any) => {
    const { Box } = $.ui.resolve(e)
    return <Box />
  })
  on('turn.step', async function* ($: any, e: any) {
    w.sent.push(e.effort)
    return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: 'end_turn', usage: null }
  })
  return w
}

let turns = 0

/** What the person typed at the prompt, as the engine stamps it (the terminal and the desktop app alike). */
const TYPED = { wait: false, origin: { kind: 'composer' } } as const

/** One model request of the main loop (or a subagent's), at the session's `effort` setting. */
async function step($: any, effort: string | undefined, index = 0, agentId?: string) {
  const stream = $.turn.step({
    turnId: `turn-${turns}`, index, model: 'claude-opus-5-5', messageCount: 3,
    ...(effort !== undefined ? { effort } : {}), ...(agentId ? { agentId } : {}),
  })
  for await (const _ of stream) {
    // drain
  }
  return stream.result
}

/** A typed message, then the turn's first request at `effort`. */
async function send($: any, text: string, effort: string | undefined) {
  turns += 1
  await $.prompt.submit({ text, ...TYPED })
  await step($, effort)
}

const ASK = { typesafe_api_key: 'k', ask_first: true }
const PLAIN = { typesafe_api_key: 'k' }

describe('judging', () => {
  test('asks Jev with the key, the message and the latest reply', { options: ASK }, async ($, on) => {
    const w = world(on, { rows: [{ role: 'user', text: 'fix it' }, { role: 'assistant', text: 'Found it. Patch?' }] })
    mock.clock(on)
    await send($, 'yes, and add a test', 'high')
    expect(w.jevCalls.length).toBe(1)
    expect(w.jevCalls[0]?.url).toBe('https://api.typesafe.ai/v1/systemone')
    expect(w.jevCalls[0]?.auth).toBe('Bearer k')
    expect(w.jevCalls[0]?.body.state.new_message).toBe('yes, and add a test')
    expect(w.jevCalls[0]?.body.state.previous_reply).toBe('Found it. Patch?')
  })

  test('slash commands are not judged', { options: ASK }, async ($, on) => {
    const w = world(on, {})
    mock.clock(on)
    await send($, '/effort high', 'low')
    expect(w.jevCalls.length).toBe(0)
    expect(w.asked.length).toBe(0)
  })

  test('task notifications and SDK turns are not judged', { options: ASK }, async ($, on) => {
    const w = world(on, {})
    mock.clock(on)
    await $.prompt.submit({ text: '<task-notification>done</task-notification>', wait: false, origin: { kind: 'task-notification' } })
    await $.prompt.submit({ text: 'The app was quit while you were working. Please continue.', wait: false, origin: { kind: 'sdk' } })
    await step($, 'low')
    expect(w.jevCalls.length).toBe(0)
    expect(w.sent).toEqual(['low'])
  })

  test("a verdict never carries over to another prompt's turn", { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)] })
    mock.clock(on)
    await $.prompt.submit({ text: 'fix the flaky integration test', ...TYPED }) // interrupted before Claude's first request
    await $.prompt.submit({ text: '<task-notification>done</task-notification>', wait: false, origin: { kind: 'task-notification' } })
    await step($, 'low')
    expect(w.asked.length).toBe(0)
    expect(w.sent).toEqual(['low'])
  })

  test('a message starting with a path is judged', { options: ASK }, async ($, on) => {
    const w = world(on, {})
    mock.clock(on)
    await send($, '/Users/me/app/server.py crashes on start', 'high')
    expect(w.jevCalls.length).toBe(1)
  })
})

describe('ask_first', () => {
  test('switch: the request and the rest of the session run at the new level', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)], pick: 0 })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low')
    expect(w.asked.length).toBe(1)
    expect(w.asked[0]).toContain('high')
    expect(w.sent).toEqual(['high'])
    expect(w.statuses.at(-1)).toBe('✓ effort: high fits this (0.99) · now high · sending high (your setting: low)')
    await step($, 'low', 1)
    expect(w.sent).toEqual(['high', 'high'])
  })

  test('running /effort takes back control, even at the level the session had', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)], pick: 0 })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low') // switched to high
    await $.command.run({ command: 'effort', args: 'low', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 100 } })
    expect(w.statuses.at(-1)).toBe('○ effort: back on your setting')
    await step($, 'low', 1)
    expect(w.sent).toEqual(['high', 'low'])
  })

  test('while a switch is in effect, every line says so', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97), 500], pick: 0, classify: undefined })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low') // switched to high
    await send($, 'continue', 'low') // a go-ahead with nothing to size it from
    expect(w.statuses.at(-1)).toBe('○ effort: go-ahead · keep your level · sending high (your setting: low)')
    await send($, 'and the next one', 'low') // Jev fails
    expect(w.statuses.at(-1)).toBe("○ effort: no tip this time (Jev didn't answer) · sending high (your setting: low)")
    expect(w.sent).toEqual(['high', 'high', 'high'])
  })

  test('the setting under the input box takes back control', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97), jev('high', 0.97)], pick: 0 })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low') // switched to high
    await step($, 'medium', 1) // the person moved the bar to medium
    expect(w.sent).toEqual(['high', 'medium'])
    expect(w.statuses[w.statuses.length - 1]).toContain('back on your setting, medium')
    await step($, 'low', 2)
    expect(w.sent[2]).toBe('low') // the override is gone for good
  })

  test('keep: no second question for the same direction from the same level', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97), jev('max', 0.95)], pick: 1 })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low')
    expect(w.asked.length).toBe(1)
    expect(w.sent).toEqual(['low'])
    await send($, 'now audit the whole module', 'low') // Jev moved to max: same direction
    expect(w.asked.length).toBe(1)
    expect(w.sent).toEqual(['low', 'low'])
    expect(w.statuses[w.statuses.length - 1]).toContain('you chose low')
  })

  test('a turned-down switch is forgotten once the level changes', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97), jev('medium', 0.97), jev('high', 0.97)], pick: 1 })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low') // keep low
    await send($, 'what does this flag do?', 'medium') // the person moved to medium
    await send($, 'fix the next flaky test', 'low') // and back to low
    expect(w.asked.length).toBe(2)
  })

  test('downgrades are asked too', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('low', 0.97)], pick: 0 })
    mock.clock(on)
    await send($, 'what does git stash do?', 'max')
    expect(w.asked.length).toBe(1)
    expect(w.asked[0]).toContain('Drop to low')
    expect(w.sent).toEqual(['low'])
  })

  test('nothing asked when the level fits', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)] })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'high')
    expect(w.asked.length).toBe(0)
    expect(w.sent).toEqual(['high'])
    expect(w.statuses[w.statuses.length - 1]).toContain('✓ effort: high fits this')
  })

  test('xhigh counts as close to high and max', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('max', 0.97)] })
    mock.clock(on)
    await send($, 'build and verify the whole pipeline overnight', 'xhigh')
    expect(w.asked.length).toBe(0)
  })

  test('a dismissed dialog keeps the level and remembers nothing', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97), jev('high', 0.97)], pick: 'dismiss' })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low')
    expect(w.sent).toEqual(['low'])
    await send($, 'fix the next flaky test', 'low') // not taken as a "keep": asked again
    expect(w.asked.length).toBe(2)
  })
})

describe('the band (ask_first off)', () => {
  for (const surface of ['terminal', 'desktop'] as const) {
    test(`offers the switch and applies it from the next step (${surface})`, { options: PLAIN }, async ($, on) => {
      const w = world(on, { jev: [jev('high', 0.97)] })
      mock.clock(on)
      await send($, 'fix the flaky integration test', 'low')
      expect(w.asked.length).toBe(0)
      expect(w.sent).toEqual(['low']) // the running request isn't held up
      const band = await $.ui.mount({
        plugin: 'spending-effort-with-jev',
        surface,
        component: 'AbovePrompt',
        props: { hasSurvey: false, isWorking: true, maxRows: 10, bodyColumns: 100 } as any,
      })
      expect((await band.find({ key: 'switch' }))?.text).toContain('high')
      await band.press({ key: 'switch' })
      await step($, 'low', 1)
      expect(w.sent).toEqual(['low', 'high'])
      expect((await band.find({ key: 'switch' }))).toBe(undefined) // the band is gone
    })

    test(`keep stops offering that direction (${surface})`, { options: PLAIN }, async ($, on) => {
      const w = world(on, { jev: [jev('high', 0.97), jev('max', 0.95)] })
      mock.clock(on)
      await send($, 'fix the flaky integration test', 'low')
      const band = await $.ui.mount({
        plugin: 'spending-effort-with-jev',
        surface,
        component: 'AbovePrompt',
        props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 100 } as any,
      })
      await band.press({ key: 'keep' })
      await send($, 'now audit the whole module', 'low')
      expect(await band.find({ key: 'switch' })).toBe(undefined)
      expect(w.sent).toEqual(['low', 'low'])
    })
  }

  test('the digits work only while Claude does, on both surfaces', { options: PLAIN }, async ($, on) => {
    world(on, { jev: [jev('high', 0.97)] })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low')
    for (const surface of ['terminal', 'desktop'] as const) {
      for (const isWorking of [true, false]) {
        const band = await $.ui.mount({
          plugin: 'spending-effort-with-jev',
          surface,
          component: 'AbovePrompt',
          props: { hasSurvey: false, isWorking, maxRows: 10, bodyColumns: 100 } as any,
        })
        const buttons = await Promise.all(['switch', 'keep', 'close'].map(async key => (await band.find({ key }))?.props))
        expect(buttons.map(b => b?.hotkey)).toEqual(isWorking ? ['1', '2', '0'] : [undefined, undefined, undefined])
        // Idle buttons are drawn as buttons ("[ Switch to high ]"), not as "1: ..." lines.
        expect(buttons.map(b => b?.plain)).toEqual(isWorking ? [true, true, true] : [undefined, undefined, undefined])
        await band.unmount()
      }
    }
  })

  test('yields to a survey', { options: PLAIN }, async ($, on) => {
    world(on, { jev: [jev('high', 0.97)] })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low')
    const band = await $.ui.mount({
      plugin: 'spending-effort-with-jev',
      surface: 'terminal',
      component: 'AbovePrompt',
      props: { hasSurvey: true, isWorking: false, maxRows: 10, bodyColumns: 100 } as any,
    })
    expect(await band.find({ key: 'switch' })).toBe(undefined)
  })
})

describe('the main loop only', () => {
  test("a subagent's requests are left alone", { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)], pick: 0 })
    mock.clock(on)
    turns += 1
    await $.prompt.submit({ text: 'fix the flaky integration test', ...TYPED })
    await step($, 'low', 0, 'agent-1') // a subagent's request comes first
    expect(w.asked.length).toBe(0)
    expect(w.sent).toEqual(['low'])
    await step($, 'low', 1) // the main loop's request decides
    expect(w.asked.length).toBe(1)
    expect(w.sent).toEqual(['low', 'high'])
    await step($, 'low', 2, 'agent-1')
    expect(w.sent[2]).toBe('low')
  })
})

describe('go-aheads', () => {
  test('a bare go-ahead skips Jev and is sized from the conversation', { options: ASK }, async ($, on) => {
    const w = world(on, {
      rows: [{ role: 'user', text: 'spec it with me' }, { role: 'assistant', text: 'Phase 0: fake servers, probes, sandboxed runs. Start?' }],
      classify: 'high',
      pick: 0,
    })
    mock.clock(on)
    await send($, '继续', 'low')
    expect(w.jevCalls.length).toBe(0)
    expect(w.asked.length).toBe(1)
    expect(w.sent).toEqual(['high'])
    expect(w.statuses.at(-1)).toBe('✓ effort: high fits this (go-ahead) · now high · sending high (your setting: low)')
  })

  test("a go-ahead Jev can't place is sized the same way", { options: ASK }, async ($, on) => {
    const w = world(on, {
      jev: [{ effort: { choice: 'unclear', confidence: 0.6, probabilities: { unclear: 0.58, low: 0.2, high: 0.22 } }, handoff_ambiguous: { noul: 0 } }],
      rows: [{ role: 'assistant', text: 'Anything else? If not, I commit the spec and start phase 0.' }],
      classify: 'high',
      pick: 0,
    })
    mock.clock(on)
    await send($, '好，提交 spec，开始第 0 阶段', 'low')
    expect(w.jevCalls.length).toBe(1)
    expect(w.sent).toEqual(['high'])
  })

  test('with nothing to size from, the level stays', { options: ASK }, async ($, on) => {
    const w = world(on, { classify: undefined })
    mock.clock(on)
    await send($, 'ok', 'low')
    expect(w.asked.length).toBe(0)
    expect(w.sent).toEqual(['low'])
    expect(w.statuses[w.statuses.length - 1]).toContain('go-ahead')
  })
})

describe('failures never block a prompt', () => {
  test('Jev down: the "no tip" line, the level unchanged', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [500] })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low')
    expect(w.sent).toEqual(['low'])
    expect(w.statuses[w.statuses.length - 1]).toContain("Jev didn't answer")
  })

  test('a rejected key says so', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [401] })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low')
    expect(w.statuses[w.statuses.length - 1]).toContain('rejected the API key')
  })

  test('a Jev that never answers gives up after 6 s', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: ['hang'] })
    const clock = mock.clock(on)
    const submitted = $.prompt.submit({ text: 'fix the flaky integration test', ...TYPED })
    await clock.advance(6_000)
    await submitted
    await step($, 'low')
    expect(w.sent).toEqual(['low'])
    expect(w.statuses[w.statuses.length - 1]).toContain("Jev didn't answer")
  })

  test('a malformed answer gives the "no tip" line', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [{ effort: { choice: 'huge' } }] })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low')
    expect(w.statuses[w.statuses.length - 1]).toContain("Jev didn't answer")
  })
})

describe('quiet', () => {
  test('a fit shows nothing', { options: { ...ASK, quiet: true } }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)] })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'high')
    expect(w.statuses).toEqual([undefined])
  })

  test('a line that no longer holds is cleared, not left up', { options: { ...ASK, quiet: true } }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97), jev('high', 0.97)], pick: 1 })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low') // keep low
    expect(w.statuses.at(-1)).toBe('⬆ effort: high · you chose low')
    await send($, 'fix the next one', 'high') // the person moved to high: a fit
    expect(w.statuses.at(-1)).toBe(undefined)
  })

  test('a rejected key still shows', { options: { ...ASK, quiet: true } }, async ($, on) => {
    const w = world(on, { jev: [401] })
    mock.clock(on)
    await send($, 'fix the flaky integration test', 'low')
    expect(w.statuses.at(-1)).toContain('rejected the API key')
  })
})

describe('models without effort', () => {
  test('nothing is compared and the last line goes', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)] })
    mock.clock(on)
    await send($, 'fix the flaky integration test', undefined)
    expect(w.asked.length).toBe(0)
    expect(w.sent).toEqual([undefined])
    expect(w.statuses).toEqual([undefined])
  })
})

describe('decision log', () => {
  test('off by default', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)], pick: 0 })
    mock.clock(on)
    await send($, 'SECRET-PROMPT-TEXT fix the bug', 'low')
    expect(Object.keys(w.files).length).toBe(0)
  })

  test('an answer typed under "Other" changes nothing and is never logged', { options: { ...ASK, log_decisions: true } }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)], pick: { other: 'SECRET-ANSWER use medium' } })
    mock.clock(on)
    await send($, 'fix the bug', 'low')
    expect(w.sent).toEqual(['low'])
    const raw = Object.values(w.files).join('')
    expect(raw.includes('SECRET')).toBe(false)
    expect(raw.includes('"answer":"other"')).toBe(true)
  })

  test('numbers only, never message text', { options: { ...ASK, log_decisions: true } }, async ($, on) => {
    const w = world(on, {
      jev: [jev('high', 0.97)],
      rows: [{ role: 'assistant', text: 'SECRET-REPLY-TEXT' }],
      pick: 0,
    })
    mock.clock(on)
    await send($, 'SECRET-PROMPT-TEXT fix the bug', 'low')
    const path = '/home/test/.claude/plugins/data/spending-effort-with-jev-spending-effort-with-jev/decisions.jsonl'
    const raw = w.files[path] ?? ''
    expect(raw.includes('SECRET')).toBe(false)
    const records = raw.trim().split('\n').map(line => JSON.parse(line))
    expect(records.map(r => r.event)).toEqual(['prompt', 'decision'])
    expect(records[0].probabilities.high).toBe(0.97)
    expect(records[0].session).toBe('session-1')
    expect(records[1].chosen).toBe('high')
  })

  test('a failure is logged by its kind, never by what the response said', { options: { ...ASK, log_decisions: true } }, async ($, on) => {
    const w = world(on, { jev: [{ raw: '<html>SECRET-PAGE-TEXT</html>' }, 503] })
    mock.clock(on)
    await send($, 'fix the bug', 'low')
    await send($, 'fix the other bug', 'low')
    const path = '/home/test/.claude/plugins/data/spending-effort-with-jev-spending-effort-with-jev/decisions.jsonl'
    const raw = w.files[path] ?? ''
    expect(raw.includes('SECRET')).toBe(false)
    const errors = raw.trim().split('\n').map(line => JSON.parse(line)).filter(r => r.event === 'error')
    expect(errors.map(r => [r.error, r.status ?? null])).toEqual([['SyntaxError', null], ['HttpStatus', 503]])
  })
})
