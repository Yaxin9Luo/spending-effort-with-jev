// What Jev did for you: its API cost from the usage it reports on every
// answer, and per main-loop turn the level that ran next to the level Jev
// named. Nothing here counts Claude's own spending.
import type { JevDay, LedgerTurn } from '../types'
import { LEVELS } from './judge'

export const LEDGER_TURNS = 2000 // kept in the plugin's store, oldest dropped
export const JEV_DAYS = 90
/** TypeSafe's list price for Jev, per million tokens (typesafe.ai, October 2026): input billed, output free. */
export const JEV_USD_PER_MTOK_INPUT = 0.042
export const JEV_USD_PER_MTOK_OUTPUT = 0
const DAY_MS = 86_400_000

export function jevUsd(input: number, output: number): number {
  return (input * JEV_USD_PER_MTOK_INPUT + output * JEV_USD_PER_MTOK_OUTPUT) / 1_000_000
}

/** The day a time falls on, as a whole number of days since the epoch (UTC). */
export function dayOf(t: number): number {
  return Math.floor(t / DAY_MS)
}

/** Jev's usage with one more answer counted in its day; days older than JEV_DAYS dropped. */
export function counted(days: readonly JevDay[] | null, t: number, input: number, output: number): JevDay[] {
  const day = dayOf(t)
  const list = (days ?? []).filter(d => d.day > day - JEV_DAYS)
  const today = list.find(d => d.day === day)
  if (today) return list.map(d => (d.day === day ? { ...d, calls: d.calls + 1, input: d.input + input, output: d.output + output } : d))
  return [...list, { day, calls: 1, input, output }]
}

export type LevelRow = { level: string; turns: number }
export type Summary = {
  rows: LevelRow[]
  todayUsd: number
  weekUsd: number
  todayCalls: number
  weekCalls: number
  /** Turns where Jev named a level. */
  judged: number
  /** Of those, the ones that ran on Jev's level. */
  followed: number
}

const SETTINGS = [...LEVELS.slice(0, 3), 'xhigh', 'max'] as const

export function summary(turns: readonly LedgerTurn[], days: readonly JevDay[], now: number): Summary {
  const rows: LevelRow[] = SETTINGS.map(level => ({ level, turns: 0 }))
  let judged = 0
  let followed = 0
  for (const t of turns) {
    const row = rows.find(r => r.level === t.level)
    if (row) row.turns += 1
    if (t.rec === null) continue
    judged += 1
    if (t.rec === t.level || (t.level === 'xhigh' && (t.rec === 'high' || t.rec === 'max'))) followed += 1
  }
  const today = dayOf(now)
  let todayUsd = 0
  let weekUsd = 0
  let todayCalls = 0
  let weekCalls = 0
  for (const d of days) {
    const cost = jevUsd(d.input, d.output)
    if (d.day === today) {
      todayUsd += cost
      todayCalls += d.calls
    }
    if (d.day > today - 7) {
      weekUsd += cost
      weekCalls += d.calls
    }
  }
  return { rows: rows.filter(r => r.turns > 0), todayUsd, weekUsd, todayCalls, weekCalls, judged, followed }
}

export function added(turns: readonly LedgerTurn[] | null, turn: LedgerTurn): LedgerTurn[] {
  return [...(turns ?? []), turn].slice(-LEDGER_TURNS)
}

/** Dollars at the precision Jev's small amounts need. */
export function usd(x: number): string {
  const a = Math.abs(x)
  return `$${a === 0 ? '0' : a >= 1 ? a.toFixed(2) : a >= 0.01 ? a.toFixed(3) : a.toFixed(4)}`
}

/** Turns per level as pixel bars, for the desktop pane. */
export function ledgerSvg(rows: readonly LevelRow[]): string {
  const top = Math.max(...rows.map(r => r.turns), 1)
  const bars = rows.map((r, i) => {
    const h = Math.max(1, Math.round((r.turns / top) * 40))
    const x = i * 30
    return `<rect x="${x}" y="${48 - h}" width="22" height="${h}" fill="#D97757" shape-rendering="crispEdges"><animate attributeName="height" from="0" to="${h}" dur="0.5s"/><animate attributeName="y" from="48" to="${48 - h}" dur="0.5s"/></rect><text x="${x + 11}" y="60" font-size="9" text-anchor="middle" fill="#8a8580" font-family="monospace">${r.level}</text>`
  })
  const width = Math.max(30, rows.length * 30)
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} 62" width="${width * 2}" height="124">${bars.join('')}</svg>`
}
