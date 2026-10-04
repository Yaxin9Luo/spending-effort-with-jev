import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Ctx, Limit, Part } from '../types'
import { H, k, svg, tone } from './band'

const ctx = atom({ plugin: 'elizabeth-progress', key: 'ctx' } as const, null as Ctx | null)
const parts = atom({ plugin: 'elizabeth-progress', key: 'parts' } as const, [] as Part[])
const limits = atom({ plugin: 'elizabeth-progress', key: 'limits' } as const, [] as Limit[])
const cost = atom({ plugin: 'elizabeth-progress', key: 'cost' } as const, null as number | null)
const hist = atom({ plugin: 'elizabeth-progress', key: 'hist' } as const, [] as number[])
const compactAt = atom({ plugin: 'elizabeth-progress', key: 'compactAt' } as const, null as number | null)

export const register: Register = on => {
  // The engine sends new figures each time it measures them (every API reply): no polling.
  on('session.measure', async ($, e, next) => {
    const c = e.context
    if (c.tokens !== undefined && c.percent !== undefined) {
      await update($, ctx, () => ({ tokens: c.tokens ?? 0, window: c.window, percent: c.percent ?? 0 }))
    }
    await update($, limits, () => e.rateLimits.map(l => ({ kind: l.kind, percentUsed: l.percentUsed, resetsAt: l.resetsAt })))
    if (e.cost) {
      const usd = e.cost.usd
      await update($, cost, () => usd)
    }
    return next(e)
  })

  // After each main-loop turn: the breakdown (a local estimate, no request),
  // the auto-compact threshold, and one more point of history.
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId !== undefined) return result // a subagent's turn leaves the main context as it was
    const { context } = await $.session.usage({ breakdown: 'summary' })
    const b = context.breakdown
    const rows = (b?.categories ?? [])
      .filter(r => r.kind === 'used' && r.tokens > 0)
      .sort((x, y) => y.tokens - x.tokens)
      .slice(0, 5)
      .map(r => ({ name: r.name, tokens: r.tokens }))
    await update($, parts, () => rows)
    const threshold = b?.isAutoCompactEnabled && b.autoCompactThreshold ? b.autoCompactThreshold : null
    await update($, compactAt, () => (threshold !== null ? (threshold / context.window) * 100 : null))
    if (context.percent !== undefined) {
      const p = context.percent
      await update($, hist, h => [...h, p].slice(-40))
    }
    return result
  })

  // The band holds one tree, and plugins draw it in a chain: this one goes
  // under whatever the plugins beneath drew, never in its place.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const c = await read($, ctx)
    if (e.props.hasSurvey || c === null) return next(e)

    const below = await next(e)
    const ui = $.ui.resolve(e)
    const { Box, Text } = ui

    if (e.surface !== 'terminal' && 'Svg' in ui && ui.Svg) {
      const source = svg({
        c,
        ps: await read($, parts),
        ls: await read($, limits),
        usd: await read($, cost),
        h: await read($, hist),
        at: await read($, compactAt),
        now: await $.clock.now(),
      })
      return (
        <Box flexDirection="column">
          {below ?? null}
          <ui.Svg key="eliz" source={source} alt={`context ${c.percent}%`} height={H} isInteractive />
        </Box>
      )
    }

    const n = Math.round(c.percent / 4)
    return (
      <Box flexDirection="column">
        {below ?? null}
        <Text key="eliz" color={tone(c.percent / 100)}>
          {'━'.repeat(n)}
          <Text dimColor>{'─'.repeat(25 - n)} {k(c.tokens)} / {k(c.window)} ({c.percent}%)</Text>
        </Text>
      </Box>
    )
  })
}
