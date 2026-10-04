// What each level cost you: one row per main-loop turn, summed per level,
// and what following Jev would have changed, priced at your own averages.
import type { Level, LedgerTurn } from '../types'
import { LEVELS } from './judge'

export const LEDGER_TURNS = 2000 // kept in the plugin's store, oldest dropped
const DAY_MS = 86_400_000

export type LevelRow = { level: string; turns: number; usd: number; out: number }
export type Summary = {
  rows: LevelRow[]
  todayUsd: number
  weekUsd: number
  /** Turns where Jev named another level than the one that ran. */
  disagreed: number
  /** Of those, the ones priced: both levels have turns of their own to average. */
  priced: number
  /** Following Jev on the priced turns, in dollars: negative saves. */
  delta: number
}

const SETTINGS = [...LEVELS.slice(0, 3), 'xhigh', 'max'] as const

export function summary(turns: readonly LedgerTurn[], now: number): Summary {
  const rows: LevelRow[] = SETTINGS.map(level => ({ level, turns: 0, usd: 0, out: 0 }))
  let todayUsd = 0
  let weekUsd = 0
  for (const t of turns) {
    const row = rows.find(r => r.level === t.level)
    if (row) {
      row.turns += 1
      row.usd += t.usd
      row.out += t.out
    }
    if (now - t.t < DAY_MS) todayUsd += t.usd
    if (now - t.t < 7 * DAY_MS) weekUsd += t.usd
  }
  const avg = (level: string) => {
    const row = rows.find(r => r.level === level)
    return row && row.turns > 0 && row.usd > 0 ? row.usd / row.turns : null
  }
  let disagreed = 0
  let priced = 0
  let delta = 0
  for (const t of turns) {
    if (t.rec === null || t.rec === t.level) continue
    disagreed += 1
    const ran = avg(t.level)
    const wanted = avg(t.rec)
    if (ran === null || wanted === null) continue
    priced += 1
    delta += t.usd * (wanted / ran) - t.usd
  }
  return { rows: rows.filter(r => r.turns > 0), todayUsd, weekUsd, disagreed, priced, delta }
}

export function added(turns: readonly LedgerTurn[] | null, turn: LedgerTurn): LedgerTurn[] {
  return [...(turns ?? []), turn].slice(-LEDGER_TURNS)
}

export function usd(x: number): string {
  const sign = x < 0 ? '-' : ''
  const a = Math.abs(x)
  return `${sign}$${a >= 100 ? a.toFixed(0) : a >= 1 ? a.toFixed(2) : a.toFixed(3)}`
}

export function tokens(n: number): string {
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

/** Cost per level as pixel bars, for the desktop pane. */
export function ledgerSvg(rows: readonly LevelRow[]): string {
  const top = Math.max(...rows.map(r => r.usd), 0.0001)
  const bars = rows.map((r, i) => {
    const h = Math.max(1, Math.round((r.usd / top) * 40))
    const x = i * 30
    return `<rect x="${x}" y="${48 - h}" width="22" height="${h}" fill="#D97757" shape-rendering="crispEdges"><animate attributeName="height" from="0" to="${h}" dur="0.5s"/><animate attributeName="y" from="48" to="${48 - h}" dur="0.5s"/></rect><text x="${x + 11}" y="60" font-size="9" text-anchor="middle" fill="#8a8580" font-family="monospace">${r.level}</text>`
  })
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${Math.max(30, rows.length * 30)} 62" width="${Math.max(30, rows.length * 30) * 2}" height="124">${bars.join('')}</svg>`
}

export type { Level }
