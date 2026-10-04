// The features around the switch: the ledger, thresholds tuned to the
// person's answers, subagents sized by their task, the spec interview and
// the mid-turn downgrade hint.
import { describe, expect, mock, test } from 'claude-code/testing'

import { switchMins, tallied } from '../hooks/tuning'
import { summary } from '../hooks/ledger'

type World = {
  sent: Array<{ effort: unknown; agentId?: string }>
  asked: string[]
  statuses: Array<string | undefined>
  toasts: string[]
  contexts: Array<readonly string[] | undefined>
  spawned: Array<() => void>
  /** Resolves once a spawn reaches the engine (after the mod judged it). */
  reached: Promise<void>
  /** What the session has cost so far, as /cost would say. */
  cost: { usd: number }
}

type Setup = {
  /** Jev's answer to an effort question, in order; the last repeats. */
  jev?: Array<Record<string, unknown>>
  /** Jev's "is the rest mechanical" probability, mid-turn. */
  mechanical?: number
  /** Answers to dialogs, in order: an option's position, or typed text. */
  answers?: Array<number | string>
  /** What the small model drafts as spec questions. */
  drafted?: string
  /** Hold each spawn until `w.spawned` is called, as when the subagent's first request comes first. */
  holdSpawn?: boolean
}

function jev(choice: string, conf = 0.95, amb = 0): Record<string, unknown> {
  const others = ['low', 'medium', 'high', 'max'].filter(lv => lv !== choice)
  const probabilities: Record<string, number> = Object.fromEntries(others.map(lv => [lv, (1 - conf) / others.length]))
  probabilities[choice] = conf
  return { effort: { choice, confidence: conf, probabilities }, handoff_ambiguous: { noul: amb } }
}

const TYPED = { wait: false, origin: { kind: 'composer' } } as const

function world(on: any, setup: Setup): World {
  const w: World = { sent: [], asked: [], statuses: [], toasts: [], contexts: [], spawned: [], reached: Promise.resolve(), cost: { usd: 1 } }
  let reach = () => {}
  w.reached = new Promise<void>(r => (reach = r))
  const answers = setup.jev ?? [jev('high')]
  const dialog = [...(setup.answers ?? [])]
  let call = 0
  mock.env(on, { HOME: '/home/test' })
  mock.store(on)
  on('prompt.submit', ($: any, e: any) => {
    w.contexts.push(e.context)
    return { text: e.text }
  })
  on('session.messages', () => ({ value: [] }))
  on('session.id', () => ({ value: 'session-1' }))
  on('session.usage', () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 0, window: 200_000, percent: 0 }, cost: { usd: w.cost.usd } } }))
  on('http.fetch', ($: any, e: any) => {
    const body = JSON.parse(e.init?.body ?? '{}')
    if (body.questions?.rest_is_mechanical) {
      return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ answers: { rest_is_mechanical: { noul: setup.mechanical ?? 0 } } }) } }
    }
    const answer = answers[Math.min(call, answers.length - 1)]
    call += 1
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ answers: answer }) } }
  })
  on('model.complete', () => ({ value: { isAnswered: true, text: setup.drafted ?? '', usage: {} } }))
  on('tool.call', { tool: 'AskUserQuestion' }, ($: any, e: any) => {
    const q = e.questions[0]
    w.asked.push(q.question)
    const pick = dialog.shift() ?? 0
    if (pick === 'dismiss') return { deny: 'dismissed' }
    const answer = typeof pick === 'string' ? pick : q.options[pick].label
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
  on('ui.open', () => ({ value: { isPlaced: true, id: 'effort-ledger', title: 'Effort ledger' } }))
  on('ui.render', { component: 'AbovePrompt' }, ($: any, e: any) => {
    const { Box } = $.ui.resolve(e)
    return <Box />
  })
  on('ui.render', { component: 'Pane' }, ($: any, e: any) => {
    const { Box } = $.ui.resolve(e)
    return <Box />
  })
  on('agent.spawn', ($: any, e: any) => {
    const result = { model: 'claude-opus-5-5', agentId: `agent-${e.description}` }
    reach()
    return setup.holdSpawn ? new Promise(resolve => w.spawned.push(() => resolve(result))) : result
  })
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', ($: any, e: any) => ({ text: e.answer }))
  on('turn.step', async function* ($: any, e: any) {
    w.sent.push({ effort: e.effort, ...(e.agentId ? { agentId: e.agentId } : {}) })
    return { turnId: e.turnId, index: e.index, answer: 'Running the tests.', toolUses: [{ name: 'Bash', input: {} }], stopReason: 'end_turn', usage: null }
  })
  return w
}

let turns = 0

async function step($: any, turnId: string, effort: string, index: number, agentId?: string) {
  const stream = $.turn.step({ turnId, index, model: 'claude-opus-5-5', effort, messageCount: 3, ...(agentId ? { agentId } : {}) })
  for await (const _ of stream) {
    // drain
  }
  return stream.result
}

/** A typed message, its turn's first request at `effort`, and the turn's end at `usd` spent. */
async function turn($: any, w: World, text: string, effort: string, spent = 0.25, steps = 1) {
  turns += 1
  const turnId = `turn-${turns}`
  await $.prompt.submit({ text, ...TYPED })
  await $.turn.start({ text, turnId })
  for (let i = 0; i < steps; i++) await step($, turnId, effort, i)
  w.cost.usd += spent
  await $.turn.complete({ reason: 'answer', answer: 'done', durationMs: 1, isAborted: false, turnId, usage: { input_tokens: 1, output_tokens: 1200, cache_read_input_tokens: 0, cache_creation_input_tokens: 0, model: 'claude-opus-5-5' } })
  return turnId
}

const BASE = { typesafe_api_key: 'k' }
const ASK = { ...BASE, ask_first: true }
const PANE = { plugin: 'spending-effort-with-jev', component: 'Pane', requestId: 'effort-ledger', props: {} as any } as const

describe('the ledger', () => {
  test('each turn adds a row priced from /cost, and the pane sums them', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97), jev('low', 0.97)], answers: [0, 1] })
    mock.clock(on)
    await turn($, w, 'fix the flaky integration test', 'low', 0.4) // switched to high
    await turn($, w, 'what does this flag do?', 'low', 0.05) // Jev: low, but the switch holds: kept high
    for (const surface of ['terminal', 'desktop'] as const) {
      const pane = await $.ui.mount({ ...PANE, surface })
      expect((await pane.find({ text: /today \$0\.450/ })) !== undefined).toBe(true)
      expect((await pane.find({ text: /^high\s+2 turns/ })) !== undefined).toBe(true)
      expect((await pane.find({ text: /Jev named another level on 1 turn\./ })) !== undefined).toBe(true)
      if (surface === 'desktop') expect(await pane.find({ type: 'Svg' })).toBeDefined()
      await pane.unmount()
    }
  })

  test('the band opens it', { options: ASK }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)] })
    mock.clock(on)
    await turn($, w, 'fix the flaky integration test', 'high')
    const band = await $.ui.mount({ plugin: 'spending-effort-with-jev', surface: 'desktop', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 100 } as any })
    await band.press({ key: 'ledger' })
    await band.unmount()
  })

  test('following Jev is priced at your own averages', () => {
    const now = 10_000_000_000
    const rows = [
      { t: now, level: 'high', rec: 'high', usd: 1, out: 0 },
      { t: now, level: 'low', rec: 'low', usd: 0.1, out: 0 },
      { t: now, level: 'high', rec: 'low', usd: 1, out: 0 }, // would have cost 0.1 on low
    ]
    const sum = summary(rows, now)
    expect(sum.disagreed).toBe(1)
    expect(sum.priced).toBe(1)
    expect(Math.round(sum.delta * 100) / 100).toBe(-0.9)
  })
})

describe('the band', () => {
  test('beside the verdict: the cost of this turn and today, and subagents; nothing of Claude Code\'s own usage', { options: BASE }, async ($, on) => {
    const w = world(on, { jev: [jev('low', 0.97)] })
    mock.clock(on)
    turns += 1
    const turnId = `turn-${turns}`
    await $.prompt.submit({ text: 'what does this flag do?', ...TYPED })
    await $.turn.start({ text: 'what does this flag do?', turnId })
    await step($, turnId, 'low', 0)
    await $.agent.spawn({ tool_use_id: 't1', prompt: 'find x', description: 'find', subagentType: 'Explore', provider: { plugin: 'engine', tier: 'core' }, parentModel: 'claude-opus-5-5', background: false, fork: false } as any)
    w.cost.usd += 0.12
    const wide = await $.ui.mount({ plugin: 'spending-effort-with-jev', surface: 'desktop', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: true, maxRows: 10, bodyColumns: 160 } as any })
    const text = JSON.stringify(await wide.drawn())
    for (const fact of ['low fits · now low (0.97)', 'turn $0.120', 'today $0.120', 'subagents low']) expect(text).toContain(fact)
    for (const fact of ['context', 'limit']) expect(text).not.toContain(fact)
    await wide.unmount()
    const narrow = await $.ui.mount({ plugin: 'spending-effort-with-jev', surface: 'terminal', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: true, maxRows: 10, bodyColumns: 60 } as any })
    expect(JSON.stringify(await narrow.drawn())).not.toContain('today')
  })
})

describe('thresholds tuned to your answers', () => {
  test('taken offers come sooner, turned-down ones later, only after ten', () => {
    let t = null
    for (let i = 0; i < 9; i++) t = tallied(t, 'up', false)
    expect(switchMins(t, true).up).toBe(0.7)
    t = tallied(t, 'up', false)
    expect(switchMins(t, true).up).toBe(0.85)
    expect(switchMins(t, false).up).toBe(0.7)
    let d = null
    for (let i = 0; i < 10; i++) d = tallied(d, 'down', true)
    expect(switchMins(d, true).down).toBe(0.6)
    expect(switchMins(d, true).up).toBe(0.7)
  })

  test('after ten turned-down upgrades, a 0.8 upgrade is no longer asked', { options: ASK }, async ($, on) => {
    const split = { effort: { choice: 'high', confidence: 0.8, probabilities: { high: 0.8, low: 0.2 } }, handoff_ambiguous: { noul: 0 } }
    const w = world(on, { jev: [split], answers: Array(12).fill(1) })
    mock.clock(on)
    for (let i = 0; i < 10; i++) {
      await turn($, w, `fix flaky test ${i}`, i % 2 === 0 ? 'low' : 'medium') // a new level each time: asked again
    }
    expect(w.asked.length).toBe(10)
    await turn($, w, 'fix flaky test 10', 'low')
    expect(w.asked.length).toBe(10)
  })
})

describe('subagents', () => {
  test('a lookup runs on low, a heavy task on high at most, the main loop untouched', { options: BASE }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97), jev('low', 0.97), jev('max', 0.97)] })
    mock.clock(on)
    turns += 1
    await $.prompt.submit({ text: 'fix the flaky integration test', ...TYPED })
    await step($, `turn-${turns}`, 'high', 0)
    await $.agent.spawn({ tool_use_id: 't1', prompt: 'find where retry is defined', description: 'find', subagentType: 'Explore', provider: { plugin: 'engine', tier: 'core' }, parentModel: 'claude-opus-5-5', background: false, fork: false } as any)
    await $.agent.spawn({ tool_use_id: 't2', prompt: 'audit the auth module end to end', description: 'audit', subagentType: 'general-purpose', provider: { plugin: 'engine', tier: 'core' }, parentModel: 'claude-opus-5-5', background: false, fork: false } as any)
    await step($, 'sub', 'high', 0, 'agent-find')
    await step($, 'sub2', 'low', 0, 'agent-audit')
    await step($, `turn-${turns}`, 'high', 1)
    expect(w.sent.map(x => x.effort)).toEqual(['high', 'low', 'high', 'high'])
    expect(w.toasts.some(t => t.includes('"find" on low'))).toBe(true)
  })

  test("a subagent's first request, sent before its spawn returns, is sized too", { options: BASE }, async ($, on) => {
    const w = world(on, { jev: [jev('low', 0.97)], holdSpawn: true })
    mock.clock(on)
    const spawn = $.agent.spawn({ tool_use_id: 't9', prompt: 'find where retry is defined', description: 'early', subagentType: 'Explore', provider: { plugin: 'engine', tier: 'core' }, parentModel: 'claude-opus-5-5', background: false, fork: false } as any)
    await w.reached // judged, now spawning
    await step($, 'sub', 'high', 0, 'agent-early') // the subagent's first request
    w.spawned.forEach(go => go())
    await spawn
    await step($, 'sub', 'high', 1, 'agent-early')
    expect(w.sent.map(x => x.effort)).toEqual(['low', 'low'])
  })

  test('off when the option is off', { options: { ...BASE, subagents: false } }, async ($, on) => {
    const w = world(on, { jev: [jev('low', 0.97)] })
    mock.clock(on)
    await $.agent.spawn({ tool_use_id: 't1', prompt: 'find x', description: 'find', subagentType: 'Explore', provider: { plugin: 'engine', tier: 'core' }, parentModel: 'claude-opus-5-5', background: false, fork: false } as any)
    await step($, 'sub', 'high', 0, 'agent-find')
    expect(w.sent.map(x => x.effort)).toEqual(['high'])
  })
})

describe('the spec interview', () => {
  test('a fuzzy long hand-off asks drafted questions and hands Claude the answers', { options: BASE }, async ($, on) => {
    const w = world(on, {
      jev: [jev('max', 0.9, 0.9)],
      drafted: '1. What counts as done for the migration?\n2. Which services must not restart?\n3. Should it open a PR or push?',
      answers: ['all tests green and the staging deploy healthy', 0, 1],
    })
    mock.clock(on)
    await $.prompt.submit({ text: 'migrate everything to the new queue overnight, do it all', ...TYPED })
    expect(w.asked).toEqual(['What counts as done for the migration?', 'Which services must not restart?', 'Should it open a PR or push?'])
    const context = w.contexts.at(-1) ?? []
    expect(context.join('\n')).toContain('A: all tests green and the staging deploy healthy')
    expect(context.join('\n')).not.toContain('Which services') // left to Claude: not passed on
  })

  test('nothing is asked for a clear message', { options: BASE }, async ($, on) => {
    const w = world(on, { jev: [jev('max', 0.9, 0.1)] })
    mock.clock(on)
    await $.prompt.submit({ text: 'build and verify the pipeline overnight; done = CI green', ...TYPED })
    expect(w.asked.length).toBe(0)
    expect(w.contexts.at(-1)).toBe(undefined)
  })

  test('standard questions when the small model has none', { options: BASE }, async ($, on) => {
    const w = world(on, { jev: [jev('max', 0.9, 0.9)], drafted: '', answers: [1] })
    mock.clock(on)
    await $.prompt.submit({ text: 'just do the whole refactor', ...TYPED })
    expect(w.asked[0]).toContain('What does done look like')
  })
})

describe('the mid-turn hint', () => {
  test('a long high turn whose rest is mechanical offers low for that turn only', { options: BASE }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)], mechanical: 0.92 })
    mock.clock(on)
    turns += 1
    const turnId = `turn-${turns}`
    await $.prompt.submit({ text: 'fix the flaky integration test', ...TYPED })
    await $.turn.start({ text: 'fix the flaky integration test', turnId })
    for (let i = 0; i <= 4; i++) await step($, turnId, 'high', i)
    const band = await $.ui.mount({ plugin: 'spending-effort-with-jev', surface: 'terminal', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: true, maxRows: 10, bodyColumns: 100 } as any })
    expect((await band.find({ text: /looks mechanical/ })) !== undefined).toBe(true)
    await band.press({ key: 'switch' })
    await step($, turnId, 'high', 5)
    await $.turn.complete({ reason: 'answer', answer: 'done', durationMs: 1, isAborted: false, turnId })
    await turn($, w, 'next task', 'high')
    expect(w.sent.map(x => x.effort)).toEqual(['high', 'high', 'high', 'high', 'high', 'low', 'high'])
  })

  test('not offered when the rest still needs thought, nor on low', { options: BASE }, async ($, on) => {
    const w = world(on, { jev: [jev('high', 0.97)], mechanical: 0.3 })
    mock.clock(on)
    await turn($, w, 'fix the flaky integration test', 'high', 0.1, 6)
    const band = await $.ui.mount({ plugin: 'spending-effort-with-jev', surface: 'terminal', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: true, maxRows: 10, bodyColumns: 100 } as any })
    expect(await band.find({ text: /looks mechanical/ })).toBe(undefined)
  })
})
