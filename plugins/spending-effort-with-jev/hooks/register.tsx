// spending-effort-with-jev as a mod: judge each typed message with Jev, then,
// before the model request that would run it, compare with the live effort
// and let the person switch from the UI. The switch rewrites the effort of
// this session's main-loop requests; the setting under the input box is
// untouched, and changing it there takes back control.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, SessionMessage } from 'claude-code'

import type { Answers, Declined, Level, Offer, Override, Pending } from '../types'
import {
  JEV_URL,
  LEVELS,
  TIMEOUT_MS,
  VERSION,
  WORDS,
  certain,
  checked,
  goAheadText,
  isGoAhead,
  isPersonOrigin,
  isTyped,
  jevBody,
  lang,
  recentTurns,
  statusLine,
  verdict,
} from './judge'
import type { Lang, Turn, Verdict } from './judge'

const pending = atom({ plugin: 'spending-effort-with-jev', key: 'pending' } as const, null as Pending | null)
const override = atom({ plugin: 'spending-effort-with-jev', key: 'override' } as const, null as Override | null)
const declined = atom({ plugin: 'spending-effort-with-jev', key: 'declined' } as const, {} as Declined)
const lastLevel = atom({ plugin: 'spending-effort-with-jev', key: 'lastLevel' } as const, null as string | null)
const offer = atom({ plugin: 'spending-effort-with-jev', key: 'offer' } as const, null as Offer | null)
const warnedNoKey = atom({ plugin: 'spending-effort-with-jev', key: 'warnedNoKey' } as const, false)

const GO_AHEAD_TOKENS = 6000 // a go-ahead's plan can sit a few messages back
const SIZE_TIMEOUT_MS = 6000 // with Jev's 6 s, a message waits 12 s at most, as with the v0.2 hook
const LOG_MAX_CHARS = 1_000_000

type Settings = { l: Lang; quiet: boolean; askFirst: boolean; logOn: boolean; key: string }

class HttpStatus extends Error {
  name = 'HttpStatus'
  status: number
  constructor(status: number) {
    super(`HTTP ${status}`)
    this.status = status
  }
}

class Timeout extends Error {
  name = 'Timeout'
}

export const register: Register = (on, options) => {
  const s: Settings = {
    l: lang(options.language),
    quiet: options.quiet === true,
    askFirst: options.ask_first === true,
    logOn: options.log_decisions === true,
    key: typeof options.typesafe_api_key === 'string' ? options.typesafe_api_key : '',
  }

  on('prompt.submit', async ($, e, next) => {
    const text = e.text.trim()
    if (isPersonOrigin(e.origin) && isTyped(text)) await judge($, text, s)
    // A verdict is for its own message's turn, never a later prompt's.
    else await update($, pending, () => null)
    return next(e)
  })

  // The main loop's requests: the first one after a judged message decides;
  // every one carries the level the person chose here, if any.
  on('turn.step', async function* ($, e, next) {
    if (e.agentId !== undefined) return yield* next(e)
    const effort = await levelFor($, e.effort, s)
    if (effort === undefined || effort === e.effort) return yield* next(e)
    return yield* next({ ...e, effort: effort as Level })
  })

  // Running /effort, whatever level it picks (even the one the session had),
  // hands effort back to the person.
  on('command.run', { command: 'effort' }, async ($, e, next) => {
    const result = await next(e)
    await release($, s)
    return result
  })

  // With ask_first off, a switch is offered above the prompt: 1 switches from
  // Claude's next step, 2 keeps the level and stops offering that direction.
  // The digits work only while Claude does: a bare digit typed in an empty
  // prompt presses a band Button, and once the turn is over that digit is
  // more likely an answer to Claude ("1"). Clicking still works then.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const o = await read($, offer)
    if (o === null || e.props.hasSurvey) return next(e)
    const w = WORDS[s.l]
    // Working: "1: Switch to high". After the turn: "[ Switch to high ]", no digit.
    const look = (d: string) => (e.props.isWorking ? { hotkey: d, plain: true as const } : {})
    const { Box, Text, Button } = $.ui.resolve(e)
    return (
      <Box flexDirection="row">
        <Text>{w.band(o)}  </Text>
        <Button key="switch" {...look('1')} label={w.switchTo(o.level)} onPress={() => acceptOffer($, o, s)} />
        <Text>  </Text>
        <Button key="keep" {...look('2')} label={w.keep(o.from)} onPress={() => declineOffer($, o, s)} />
        <Text>  </Text>
        <Button key="close" {...look('0')} role="dismiss" label={w.close} onPress={() => closeOffer($)} />
      </Box>
    )
  })
}

// ------------------------------------------------------------- judging

/** Judge a typed message and leave the answer for the next model request. */
async function judge($: EngineInterface, text: string, s: Settings) {
  await update($, offer, () => null) // a new message replaces an unanswered offer
  const t = await $.clock.now()
  if (!s.key) {
    await update($, pending, () => null)
    if (!(await read($, warnedNoKey))) {
      await update($, warnedNoKey, () => true)
      $.ui.toast(WORDS[s.l].noKey)
    }
    return
  }
  try {
    const messages = await $.session.messages()
    const rows = Array.isArray(messages) ? messages : []
    const recent = recentTurns(rows)
    if (isGoAhead(text)) {
      const level = await sizeGoAhead($, rows, text)
      await update($, pending, () => ({ answers: level ? certain(level) : null, isGoAhead: true, t }))
      await log($, s, { event: 'prompt', goAhead: 'exact', sized: level, message_chars: text.length })
      return
    }
    let answers: Answers | null = await askJev($, s.key, text, recent)
    let goAhead = false
    if (verdict(answers, null).kind === 'unclear' && recent.length > 0) {
      // A go-ahead in words Jev can't place ("OK, commit the spec and start
      // phase 0"): the work it starts was planned earlier, often in files.
      const level = await sizeGoAhead($, rows, text)
      await log($, s, jevRecord(answers, text, recent, { goAhead: 'unclear', sized: level }))
      answers = level ? certain(level) : null
      goAhead = true
    } else {
      await log($, s, jevRecord(answers, text, recent, {}))
    }
    await update($, pending, () => ({ answers, isGoAhead: goAhead, t }))
  } catch (err) {
    const status = err instanceof HttpStatus ? err.status : undefined
    const failure: Pending['failure'] = status === 401 || status === 403 ? 'badKey' : 'error'
    await update($, pending, () => ({ answers: null, isGoAhead: false, failure, t }))
    // The kind of failure only: a parser's message can quote the response.
    await log($, s, { event: 'error', error: err instanceof Error ? err.name : 'unknown', status })
  }
}

async function askJev($: EngineInterface, key: string, text: string, recent: readonly Turn[]): Promise<Answers> {
  const response = await within(
    $,
    TIMEOUT_MS,
    $.http.fetch(JEV_URL, {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(jevBody(text, recent)),
    }),
  )
  if (!response.ok) throw new HttpStatus(response.status)
  return checked(JSON.parse(response.text).answers)
}

/** A go-ahead's work is in the conversation, not in its words: a small model sizes it. */
async function sizeGoAhead($: EngineInterface, rows: readonly SessionMessage[], text: string): Promise<Level | null> {
  const recent = recentTurns(rows, GO_AHEAD_TOKENS)
  if (recent.length === 0) return null
  try {
    const label = await within($, SIZE_TIMEOUT_MS, $.model.classify(goAheadText(recent, text), LEVELS))
    return label !== undefined && (LEVELS as readonly string[]).includes(label) ? (label as Level) : null
  } catch {
    return null
  }
}

/** Resolve with `work`, or reject after `ms` (neither wait counts against the hook's budget). */
async function within<T>($: EngineInterface, ms: number, work: Promise<T>): Promise<T> {
  let timer: { cancel: () => void } | undefined
  const timeout = new Promise<never>((_, reject) => {
    timer = $.clock.after(ms, () => reject(new Timeout(`no answer in ${ms} ms`)))
  })
  work.catch(() => undefined) // a late rejection after the timeout won is nobody's
  try {
    return await Promise.race([work, timeout])
  } finally {
    timer?.cancel()
  }
}

// ------------------------------------------------------------- deciding

/** The effort to send on this main-loop request; undefined leaves it alone. */
async function levelFor($: EngineInterface, setting: unknown, s: Settings): Promise<string | undefined> {
  if (typeof setting !== 'string') {
    // A model without effort, or a token budget: nothing to compare or switch.
    if ((await read($, pending)) !== null) {
      await update($, pending, () => null)
      $.ui.status(undefined)
    }
    return undefined
  }
  const ov = await read($, override)
  // The person changed the setting themselves: theirs wins.
  if (ov !== null && ov.base !== setting) await release($, s, setting)
  const level = ov !== null && ov.base === setting ? ov.level : setting
  if ((await read($, lastLevel)) !== level) {
    // A turned-down switch holds only while the level it was turned down on does.
    await update($, declined, () => ({}))
    await update($, lastLevel, () => level)
  }
  const p = await read($, pending)
  if (p === null) return level
  await update($, pending, () => null)
  return decide($, p, setting, level, s)
}

async function decide($: EngineInterface, p: Pending, setting: string, level: string, s: Settings): Promise<string> {
  const w = WORDS[s.l]
  let line: string
  let chosen = level
  let isNews = false // what quiet still shows: a switch, a hand-off warning, a rejected key
  if (p.failure !== undefined) {
    line = p.failure === 'badKey' ? w.badKey : w.error
    isNews = p.failure === 'badKey'
  } else if (p.answers === null) {
    line = p.isGoAhead ? w.goAhead : w.unclear
  } else {
    ;[line, chosen, isNews] = await weigh($, p.answers, p.isGoAhead, setting, level, s)
  }
  const suffix = chosen !== setting ? ' ' + w.sending(chosen, setting) : ''
  // A status line stays until replaced: one quiet doesn't show is cleared, not left stale.
  $.ui.status(!s.quiet || isNews || suffix !== '' ? line + suffix : undefined)
  return chosen
}

/** Jev's answer against the level: the line, the level to send, and whether it is news. */
async function weigh(
  $: EngineInterface,
  answers: Answers,
  isGoAhead: boolean,
  setting: string,
  level: string,
  s: Settings,
): Promise<[string, string, boolean]> {
  const w = WORDS[s.l]
  const v: Verdict = { ...verdict(answers, level), sized: isGoAhead }
  if (v.kind === 'ambiguous') $.ui.toast(w.ambiguous)
  let line = statusLine(s.l, v, level)
  let chosen = level
  let answer = 'none'
  const isSwitch = (v.kind === 'up' || v.kind === 'down') && v.level !== null
  if (isSwitch) {
    const dir = v.kind as 'up' | 'down'
    const target = v.level as Level
    const turnedDown = await read($, declined)
    if (turnedDown[dir] === level) {
      line = w.stayed(v, level)
      answer = 'declined-before'
    } else if (s.askFirst) {
      const yes = w.switchTo(target)
      const no = w.keep(level)
      try {
        const picked = await $.ui.ask(w.question(v, level), { options: [yes, no], header: w.header })
        // Text typed under "Other" is the person's words: never kept or logged.
        answer = picked === yes ? 'switch' : picked === no ? 'keep' : 'other'
      } catch {
        answer = 'dismissed'
      }
      if (answer === 'switch') {
        chosen = await switchTo($, target, setting)
        // The share that backed the switch, not a made-up certainty.
        line = w.match({ ...v, kind: 'match', level: target }, chosen)
      } else if (answer === 'keep') {
        await update($, declined, d => ({ ...d, [dir]: level }))
        line = w.stayed(v, level)
      }
    } else {
      await update($, offer, () => ({ direction: dir, level: target, from: level, setting, share: v.share }))
      answer = 'offered'
    }
  }
  await log($, s, {
    event: 'decision', kind: v.kind, rec: v.level, share: round(v.share), setting, level, chosen,
    answer, goAhead: isGoAhead, ask_first: s.askFirst,
  })
  return [line, chosen, isSwitch || v.kind === 'ambiguous']
}

/** The person took effort into their own hands: stop rewriting, drop any offer. */
async function release($: EngineInterface, s: Settings, setting?: string) {
  await update($, offer, () => null)
  if ((await read($, override)) === null) return
  await update($, override, () => null)
  $.ui.status(WORDS[s.l].released(setting))
}

async function switchTo($: EngineInterface, level: string, setting: string): Promise<string> {
  await update($, override, () => (level === setting ? null : { level, base: setting }))
  await update($, offer, () => null)
  return level
}

async function acceptOffer($: EngineInterface, o: Offer, s: Settings) {
  await switchTo($, o.level, o.setting)
  $.ui.status(WORDS[s.l].switched(o.level, o.setting))
  await log($, s, { event: 'offer', answer: 'switch', rec: o.level, from: o.from, setting: o.setting })
}

async function declineOffer($: EngineInterface, o: Offer, s: Settings) {
  await update($, declined, d => ({ ...d, [o.direction]: o.from }))
  await update($, offer, () => null)
  await log($, s, { event: 'offer', answer: 'keep', rec: o.level, from: o.from, setting: o.setting })
}

async function closeOffer($: EngineInterface) {
  await update($, offer, () => null)
}

// ------------------------------------------------------------- the log

function round(x: number): number {
  return Math.round(x * 10_000) / 10_000
}

function jevRecord(a: Answers, text: string, recent: readonly Turn[], extra: Record<string, unknown>) {
  return {
    event: 'prompt', choice: a.effort.choice, confidence: a.effort.confidence ?? null,
    probabilities: a.effort.probabilities ?? null, handoff: a.handoff_ambiguous.noul,
    message_chars: text.length, context_messages: recent.length, ...extra,
  }
}

/**
 * With log_decisions on, one line per judgement and decision: numbers and
 * states only, never the text of a message or reply. Kept at 1 MB, the
 * previous file as decisions.1.jsonl.
 */
async function log($: EngineInterface, s: Settings, record: Record<string, unknown>) {
  if (!s.logOn) return
  try {
    const home = await $.env.get('HOME')
    if (!home) return
    const dir = `${home}/.claude/plugins/data/spending-effort-with-jev-spending-effort-with-jev`
    const path = `${dir}/decisions.jsonl`
    let old = ''
    try {
      old = await $.fs.read(path)
    } catch {
      old = ''
    }
    if (old.length > LOG_MAX_CHARS) {
      await $.fs.write(`${dir}/decisions.1.jsonl`, old)
      old = ''
    }
    const line = { t: await $.clock.now(), session: await $.session.id(), version: VERSION, mod: true, ...record }
    await $.fs.write(path, old + JSON.stringify(line) + '\n')
  } catch {
    // A log that can't be written never gets in the way.
  }
}
