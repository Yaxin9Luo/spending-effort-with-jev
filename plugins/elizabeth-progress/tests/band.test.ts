// The picture on its own: Elizabeth's mood, the narrow layout, and the
// engine's limits on an Svg source.
import { describe, expect, test } from 'claude-code/testing'

import { k, svg } from '../hooks/band'
import type { View } from '../hooks/band'
import { elizabeth } from '../hooks/elizabeth'

const PARTS = [
  { name: 'Messages', tokens: 210_500 },
  { name: 'System tools', tokens: 28_700 },
  { name: 'MCP tools', tokens: 19_300 },
  { name: 'Skills', tokens: 9_100 },
  { name: 'System prompt', tokens: 5_300 },
]
const NOW = Date.UTC(2026, 9, 4, 12)

function view(percent: number, over: Partial<View> = {}): View {
  return {
    c: { tokens: percent * 10_000, window: 1_000_000, percent },
    ps: PARTS,
    ls: [
      { kind: 'five_hour', percentUsed: 20, resetsAt: new Date(NOW + 33 * 60_000).toISOString() },
      { kind: 'seven_day', percentUsed: 84, resetsAt: new Date(NOW + 35 * 3_600_000).toISOString() },
    ],
    usd: 7.23,
    h: [3, 5, 8, 12, percent],
    at: 80,
    now: NOW,
    ...over,
  }
}

const ANGER = '#c8402d'
const TEAR = '#a9c8f0'

describe('her mood follows the way to auto-compact', () => {
  test('calm below 0.8 of the threshold', () => {
    const s = svg(view(60)) // 60 / 80 = 0.75
    expect(s).not.toContain(ANGER)
    expect(s).not.toContain(TEAR)
  })

  test('angry from 0.8: the sign alternates with 💢', () => {
    const s = svg(view(66)) // 0.825
    expect(s).toContain(ANGER)
    expect(s).not.toContain(TEAR)
  })

  test('crying from 0.95', () => {
    const s = svg(view(77)) // 0.9625
    expect(s).toContain(TEAR)
  })

  test('without auto-compact, the whole window counts', () => {
    expect(svg(view(70, { at: null }))).not.toContain(ANGER) // 0.7
    expect(svg(view(85, { at: null }))).toContain(ANGER)
  })
})

describe('the layout', () => {
  test('the sign shows the percentage', () => {
    expect(svg(view(28))).toContain('>28%</text>')
  })

  test('a narrow window drops the cost column and keeps three legend entries', () => {
    const s = svg(view(28))
    const narrow = s.slice(s.indexOf('<g class="only-narrow">'))
    const wide = s.slice(s.indexOf('<g class="only-wide">'), s.indexOf('<g class="only-narrow">'))
    expect(wide).toContain('COST')
    expect(narrow).not.toContain('COST')
    expect((s.match(/<g class="wide">/g) ?? []).length).toBe(2) // legend entries 4 and 5
  })

  test('turns left from the recent rise', () => {
    expect(svg(view(28, { h: [10, 14, 18, 22, 26] }))).toContain('≈13') // (80 - 28) / 4
    expect(svg(view(28, { h: [28] }))).toContain('need 2 turns')
  })

  test('the auto-compact label steps aside as she comes near', () => {
    expect(svg(view(28))).toContain('auto-compact 80%')
    expect(svg(view(70))).not.toContain('auto-compact 80%')
  })

  test('stays far inside the engine limit on an Svg source', () => {
    expect(svg(view(97)).length).toBeLessThan(131_072 / 4)
  })

  test('her ids carry a prefix, so two of her on one page share them harmlessly', () => {
    const ids = [...elizabeth({ sign: '1%' }).matchAll(/id="([^"]+)"/g)].map(m => m[1])
    expect(ids.length).toBeGreaterThan(0)
    expect(ids.every(id => id?.startsWith('eliz-'))).toBe(true)
  })

  test('text from outside is escaped', () => {
    expect(svg(view(28, { ps: [{ name: 'a<b&c', tokens: 1 }] }))).toContain('a&lt;b&amp;c')
  })
})

describe('token counts', () => {
  test('k, M and plain', () => {
    expect(k(950)).toBe('950')
    expect(k(27_600)).toBe('27.6k')
    expect(k(1_000_000)).toBe('1M')
    expect(k(1_250_000)).toBe('1.25M')
  })
})
