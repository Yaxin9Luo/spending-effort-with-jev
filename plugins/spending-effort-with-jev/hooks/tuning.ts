// Switch thresholds tuned to the person: offers they keep taking come a
// little sooner, offers they keep turning down a little later. Each
// direction on its own, only after enough answers, never far from 0.7.
import type { Tally } from '../types'
import { SWITCH_MIN } from './judge'

export const TUNE_AFTER = 10 // answers in one direction before it moves
export const TUNE_FLOOR = 0.6
export const TUNE_CEILING = 0.85

export const NO_TALLY: Tally = { up: { offered: 0, taken: 0 }, down: { offered: 0, taken: 0 } }

/** The share of Jev's answer a switch needs, per direction. */
export function switchMins(t: Tally | null, isOn: boolean): { up: number; down: number } {
  const one = (d: { offered: number; taken: number }) => {
    if (!isOn || d.offered < TUNE_AFTER) return SWITCH_MIN
    const min = SWITCH_MIN + (0.5 - d.taken / d.offered) * 0.3
    return Math.round(Math.min(TUNE_CEILING, Math.max(TUNE_FLOOR, min)) * 100) / 100
  }
  const tally = t ?? NO_TALLY
  return { up: one(tally.up), down: one(tally.down) }
}

/** The tally after the person answered an offer in `dir`. */
export function tallied(t: Tally | null, dir: 'up' | 'down', isTaken: boolean): Tally {
  const tally = t ?? NO_TALLY
  const d = tally[dir]
  return { ...tally, [dir]: { offered: d.offered + 1, taken: d.taken + (isTaken ? 1 : 0) } }
}
