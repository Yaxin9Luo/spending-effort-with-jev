// The mod end to end through the engine: figures arrive with session.measure,
// the breakdown and history with each main-loop turn, and the band draws them
// under whatever the plugins beneath drew.
import { describe, expect, mock, test } from 'claude-code/testing'

type Setup = {
  /** What the plugins beneath draw in the band; nothing by default. */
  below?: string
}

/** The context fill `$.session.usage` reports right now; a test moves it as the conversation grows. */
type Live = { percent: number }

const WINDOW = 200_000

/** Stand in for everything beneath the plugin: the engine's band, its usage figures, the turn's end. */
function world(on: any, setup: Setup): Live {
  const live: Live = { percent: 10 }
  on('session.usage', () => {
    const percent = live.percent
    const breakdown = {
      categories: [
        { name: 'Messages', tokens: percent * 1500, color: '', isDeferred: false, kind: 'used' },
        { name: 'System tools', tokens: percent * 500, color: '', isDeferred: false, kind: 'used' },
        { name: 'Free space', tokens: WINDOW, color: '', isDeferred: false, kind: 'free' },
      ],
      autoCompactThreshold: WINDOW * 0.8,
      isAutoCompactEnabled: true,
    }
    return { value: { startedAt: 0, rateLimits: [], context: { tokens: percent * 2000, window: WINDOW, percent, breakdown } } }
  })
  on('session.measure', ($: any, e: any) => ({ changed: e.changed }))
  on('turn.complete', ($: any, e: any) => ({ text: e.answer }))
  on('ui.render', { component: 'AbovePrompt' }, ($: any, e: any) => {
    const { Box, Text } = $.ui.resolve(e)
    return setup.below === undefined ? <Box /> : <Text key="below">{setup.below}</Text>
  })
  return live
}

/** One measurement, as the engine sends it after an API reply. */
async function measure($: any, percent: number, extra: Record<string, unknown> = {}) {
  await $.session.measure({
    context: { tokens: percent * 2000, window: WINDOW, percent },
    rateLimits: [],
    changed: ['context'],
    ...extra,
  })
}

let turns = 0

/** The end of a turn: the main loop's, or a subagent's. */
async function complete($: any, agentId?: string) {
  turns += 1
  await $.turn.complete({
    reason: 'answer', answer: '', durationMs: 1, isAborted: false, turnId: `turn-${turns}`,
    usage: { input_tokens: 1, output_tokens: 1, cache_read_input_tokens: 0, cache_creation_input_tokens: 0, model: 'claude-opus-5-5' },
    ...(agentId ? { agentId } : {}),
  })
}

const BAND = { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 100 }

async function mount($: any, surface: 'terminal' | 'desktop', props: Partial<typeof BAND> = {}) {
  return $.ui.mount({ plugin: 'elizabeth-progress', surface, component: 'AbovePrompt', props: { ...BAND, ...props } as any })
}

describe('the band', () => {
  for (const surface of ['terminal', 'desktop'] as const) {
    test(`passes the band on until a first measurement (${surface})`, async ($, on) => {
      world(on, { below: 'medium is enough' })
      mock.clock(on)
      const band = await mount($, surface)
      expect(await band.find({ text: 'medium is enough' })).toBeDefined()
      expect(await band.find({ type: 'Svg' })).toBe(undefined)
      expect(await band.find({ text: /\(\d+%\)/ })).toBe(undefined)
    })

    test(`draws under what the plugins beneath draw (${surface})`, async ($, on) => {
      world(on, { below: 'medium is enough' })
      mock.clock(on)
      await measure($, 14)
      const band = await mount($, surface)
      expect(await band.find({ text: 'medium is enough' })).toBeDefined()
      if (surface === 'desktop') {
        const art = await band.find({ type: 'Svg' })
        expect(art?.props.alt).toBe('context 14%')
        expect(String(art?.props.source)).toContain('>14%</text>')
      } else {
        expect(await band.find({ text: /28\.0k \/ 200\.0k \(14%\)/ })).toBeDefined()
      }
    })

    test(`yields to a survey (${surface})`, async ($, on) => {
      world(on, {})
      mock.clock(on)
      await measure($, 14)
      const band = await mount($, surface, { hasSurvey: true })
      expect(await band.find({ type: 'Svg' })).toBe(undefined)
      expect(await band.find({ text: /\(14%\)/ })).toBe(undefined)
    })
  }

  test('shows rate limits and the session cost from the measurement', async ($, on) => {
    world(on, {})
    mock.clock(on)
    const now = Date.now()
    await measure($, 30, {
      rateLimits: [{ kind: 'five_hour', percentUsed: 20, resetsAt: new Date(now + 33 * 60_000).toISOString() }],
      cost: { usd: 7.234 },
      changed: ['context', 'rateLimits', 'cost'],
    })
    const band = await mount($, 'desktop')
    const source = String((await band.find({ type: 'Svg' }))?.props.source)
    expect(source).toContain('5H LIMIT')
    expect(source).toContain('>20%<')
    expect(source).toContain('$7.23')
  })
})

describe('each turn', () => {
  test('adds the breakdown and the auto-compact zone', async ($, on) => {
    world(on, {})
    mock.clock(on)
    await measure($, 10)
    await complete($)
    const band = await mount($, 'desktop')
    const source = String((await band.find({ type: 'Svg' }))?.props.source)
    expect(source).toContain('Messages')
    expect(source).toContain('Sys tools')
    expect(source).not.toContain('Free space') // free space is no part of the used bar
    expect(source).toContain('auto-compact 80%')
  })

  test('turns left come from the main loop alone', async ($, on) => {
    const live = world(on, {})
    mock.clock(on)
    await measure($, 10)
    await complete($)
    live.percent = 15
    await complete($, 'agent-1') // a subagent ends halfway through the next turn: no point of history
    live.percent = 20
    await complete($)
    const band = await mount($, 'desktop')
    const source = String((await band.find({ type: 'Svg' }))?.props.source)
    expect(source).toContain('+10.0%/turn') // 10 → 20 in one turn, not 10 → 15 → 20 in two
  })

  test('before two turns there is no estimate', async ($, on) => {
    world(on, {})
    mock.clock(on)
    await measure($, 10)
    await complete($)
    const band = await mount($, 'desktop')
    expect(String((await band.find({ type: 'Svg' }))?.props.source)).toContain('need 2 turns')
  })
})
