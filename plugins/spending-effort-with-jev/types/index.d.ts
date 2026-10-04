/** A level Jev picks from. xhigh is never a pick, only a session setting. */
export type Level = 'low' | 'medium' | 'high' | 'max'

/** Jev's answer, kept as plain data until the next model request. */
export type Answers = {
  effort: {
    choice: string
    confidence?: number | null
    probabilities?: Record<string, number> | null
  }
  handoff_ambiguous: { noul: number }
}

/** A judged message waiting for the next model request of the main loop. */
export type Pending = {
  /** Jev's answer; null for a bare go-ahead ("ok", "继续"), which Jev can't size. */
  answers: Answers | null
  /** The message was a go-ahead: the work it starts was planned earlier. */
  isGoAhead: boolean
  /** What the person typed, to know the same message sent again. In memory only. */
  text: string
  /** The person was asked the spec questions: the hand-off is no longer fuzzy, so max is offered for it. */
  isInterviewed?: true
  /** Why there is no answer: Jev failed, or refused the key. */
  failure?: 'error' | 'badKey'
  /** When it was judged, epoch ms. */
  t: number
}

/** The level this mod sends on the main loop's requests instead of the setting. */
export type Override = {
  level: string
  /**
   * The session's own setting the switch started from; a different one later
   * means the person changed it. Null for a switch pressed in the band: the
   * next request's setting fills it in (the person may have moved it since
   * the offer).
   */
  base: string | null
  /** The turn it was chosen in: a switch holds for that turn only. */
  turnId: string
}

/** Switches the person turned down, by direction: the level they chose to stay on. */
/** The last switch turned down: by which message, and the level kept per direction. Only that same message, sent again, isn't asked again. */
export type Declined = { text: string; up?: string; down?: string } | null

/** A switch offered in the band above the prompt (ask_first off). */
export type Offer = {
  direction: 'up' | 'down'
  level: Level
  /** The level the request was compared with (the setting, or this mod's override). */
  from: string
  /** The session's own setting at the time. */
  setting: string
  share: number
  /** The message it was offered for. */
  text: string
  /** The turn it was offered in: it goes, unanswered, when that turn ends. */
  turnId: string
  /** The mid-turn hint (the rest of a long turn looks mechanical), not a verdict on a message. */
  isMidTurn?: true
}

/** The latest verdict, drawn as a gauge above the prompt. */
export type Card = {
  /** The level the request ran on. */
  current: string
  /** Jev's level, when it names one. */
  rec: Level | null
  kind: string
  /** How much of Jev's answer backs it. */
  share?: number
}

/** Offers answered per direction: what tunes the switch thresholds. Kept across sessions. */
export type Tally = { up: { offered: number; taken: number }; down: { offered: number; taken: number } }

/** One main-loop turn in the ledger. Kept across sessions. */
export type LedgerTurn = {
  /** When it ended, epoch ms. */
  t: number
  /** The level it ran on (the last request's). */
  level: string
  /** Jev's level for the message that started it, if it named one. */
  rec: string | null
}

/** Jev's usage on one day, as its answers report it. Kept across sessions. */
export type JevDay = { day: number; calls: number; input: number; output: number }

/** The running turn's bookkeeping for the ledger and the mid-turn check. */
export type TurnNote = {
  turnId: string
  /** What the person asked, for the mid-turn check. */
  task: string
  rec: string | null
  level: string | null
  /** The steps so far, newest last: the tools each called and the end of what it said. */
  steps: Array<{ tools: string[]; said: string }>
  isChecked: boolean
}

declare module 'claude-code' {
  interface PluginState {
    'spending-effort-with-jev': {
      pending: Pending | null
      override: Override | null
      declined: Declined
      /** The level the main loop last ran on, to notice the person changing it. */
      lastLevel: string | null
      offer: Offer | null
      card: Card | null
      turn: TurnNote | null
      /** Subagents this mod sized: agentId → level. */
      agentLevels: Record<string, string>
      /**
       * Sized spawns whose agent id isn't known yet: a subagent's first request
       * can come before the spawn returns its id, so it claims the oldest one.
       */
      spawning: Array<{ id: string; level: string; agentId: string | null }>
      /** The subagents sized in the current main-loop turn, in order, for the band. */
      turnSubagents: Array<{ what: string; level: string }>
      /** Sized subagents not yet in a toast: spawns that come together share one. */
      unannounced: Array<{ what: string; level: string }>
      /** The text the latest turn started with, by turn id, for the mid-turn check. */
      started: { turnId: string; text: string } | null
      /** Bumped when the ledger changes, so the pane redraws. */
      ledgerTick: number
      /** Set once the missing-key notice was shown this session. */
      warnedNoKey: boolean
    }
  }
}
