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
}

/** Switches the person turned down, by direction: the level they chose to stay on. */
export type Declined = { up?: string; down?: string }

/** A switch offered in the band above the prompt (ask_first off). */
export type Offer = {
  direction: 'up' | 'down'
  level: Level
  /** The level the request was compared with (the setting, or this mod's override). */
  from: string
  /** The session's own setting at the time. */
  setting: string
  share: number
}

/** The latest verdict, drawn as a gauge above the prompt. */
export type Card = {
  /** The level the request ran on. */
  current: string
  /** Jev's level, when it names one. */
  rec: Level | null
  kind: string
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
      /** Set once the missing-key notice was shown this session. */
      warnedNoKey: boolean
    }
  }
}
