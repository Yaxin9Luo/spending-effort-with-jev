// spending-effort-with-jev as a mod: judge each typed message with Jev, then,
// before the model request that would run it, compare with the live effort
// and let the person switch from the UI. The switch rewrites the effort of
// this session's main-loop requests; the setting under the input box is
// untouched, and changing it there takes back control. Around that: a ledger
// of what each level cost, subagents sized by their own task, a mid-turn
// downgrade hint, a spec interview before long fuzzy runs, and thresholds
// tuned to the person's own answers.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, SessionMessage } from 'claude-code'

import type { Answers, Card, Declined, JevDay, LedgerTurn, Level, Offer, Override, Pending, Tally, TurnNote } from '../types'
import {
  AMBIGUITY_MIN,
  JEV_URL,
  LEVELS,
  MID_TURN_MIN,
  MID_TURN_STEP,
  TIMEOUT_MS,
  VERSION,
  WORDS,
  certain,
  checked,
  gaugeSvg,
  gaugeText,
  goAheadText,
  isGoAhead,
  isPersonOrigin,
  isTyped,
  jevBody,
  lang,
  midTurnBody,
  recentTurns,
  statusLine,
  subagentLevel,
  verdict,
} from './judge'
import type { Lang, Turn, Verdict } from './judge'
import { added, counted, ledgerSvg, summary, usd } from './ledger'
import { switchMins, tallied } from './tuning'

const pending = atom({ plugin: 'spending-effort-with-jev', key: 'pending' } as const, null as Pending | null)
const override = atom({ plugin: 'spending-effort-with-jev', key: 'override' } as const, null as Override | null)
const declined = atom({ plugin: 'spending-effort-with-jev', key: 'declined' } as const, {} as Declined)
const lastLevel = atom({ plugin: 'spending-effort-with-jev', key: 'lastLevel' } as const, null as string | null)
const offer = atom({ plugin: 'spending-effort-with-jev', key: 'offer' } as const, null as Offer | null)
const card = atom({ plugin: 'spending-effort-with-jev', key: 'card' } as const, null as Card | null)
const warnedNoKey = atom({ plugin: 'spending-effort-with-jev', key: 'warnedNoKey' } as const, false)
const turn = atom({ plugin: 'spending-effort-with-jev', key: 'turn' } as const, null as TurnNote | null)
const agentLevels = atom({ plugin: 'spending-effort-with-jev', key: 'agentLevels' } as const, {} as Record<string, string>)
const spawning = atom({ plugin: 'spending-effort-with-jev', key: 'spawning' } as const, [] as Array<{ id: string; level: string; agentId: string | null }>)
const started = atom({ plugin: 'spending-effort-with-jev', key: 'started' } as const, null as { turnId: string; text: string } | null)
const ledgerTick = atom({ plugin: 'spending-effort-with-jev', key: 'ledgerTick' } as const, 0)

const LEDGER_PANE = 'effort-ledger'
const GO_AHEAD_TOKENS = 6000 // a go-ahead's plan can sit a few messages back
const SIZE_TIMEOUT_MS = 6000 // with Jev's 6 s, a message waits 12 s at most, as with the v0.2 hook
const SPEC_TIMEOUT_MS = 8000
const LOG_MAX_CHARS = 1_000_000

type Settings = {
  l: Lang
  quiet: boolean
  askFirst: boolean
  logOn: boolean
  key: string
  selfTune: boolean
  subagents: boolean
  interview: boolean
  midturn: boolean
}

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
    selfTune: options.self_tune !== false,
    subagents: options.subagents !== false,
    interview: options.interview !== false,
    midturn: options.midturn !== false,
  }

  // Typed messages in the order they came: a judgement that lands after a
  // newer message's is dropped.
  const order = { latest: 0 }

  on('session.start', async ($, e, next) => {
    const result = await next(e)
    try {
      await $.command.register({ name: LEDGER_PANE, description: WORDS[s.l].ledgerTitle })
    } catch {
      // No command, but the band's button still opens the ledger.
    }
    return result
  })

  on('command.run', { command: LEDGER_PANE }, async $ => {
    await openLedger($, s)
    return { text: WORDS[s.l].ledgerOpened }
  })

  on('prompt.submit', async ($, e, next) => {
    const text = e.text.trim()
    if (isPersonOrigin(e.origin) && isTyped(text)) {
      const spec = await judge($, text, s, order)
      if (spec.length > 0) return next({ ...e, context: [...(e.context ?? []), ...spec] })
    }
    // A verdict is for its own message's turn, never a later turn's. A prompt
    // delivered into the running turn (turnId set) starts none.
    else if (e.turnId === undefined) await update($, pending, () => null)
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    await update($, started, () => ({ turnId: e.turnId, text: e.text }))
    return next(e)
  })

  // Every model request. The main loop's first one after a judged message
  // decides; each carries the level the person chose here, if any. A
  // subagent's carries the level its task was sized at.
  on('turn.step', async function* ($, e, next) {
    if (e.agentId !== undefined) {
      const sized = (await read($, agentLevels))[e.agentId] ?? (await claimSpawn($, e.agentId))
      if (sized === undefined || typeof e.effort !== 'string' || sized === e.effort) return yield* next(e)
      return yield* next({ ...e, effort: sized as Level })
    }
    await openTurn($, e.turnId, e.index)
    const effort = await levelFor($, e.effort, s)
    const sent = effort ?? (typeof e.effort === 'string' ? e.effort : null)
    if (sent !== null) await midTurnCheck($, e.turnId, e.index, sent, typeof e.effort === 'string' ? e.effort : sent, s)
    const result = effort === undefined || effort === e.effort ? yield* next(e) : yield* next({ ...e, effort: effort as Level })
    await noteStep($, e.turnId, sent, result.answer, result.toolUses.map(t => t.name))
    return result
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId === undefined) await closeTurn($, e.turnId)
    return result
  })

  // A subagent runs on a level fitting its own task: Explore-style lookups
  // low, verification high (never max: that's for the person to choose).
  on('agent.spawn', async ($, e, next) => {
    if (!s.subagents || !s.key || e.fork) return next(e)
    const level = await sizeTask($, e.prompt, s)
    if (level !== null) await update($, spawning, list => [...list, { id: e.tool_use_id, level, agentId: null }])
    const result = await next(e)
    await update($, spawning, list => list.filter(x => x.id !== e.tool_use_id))
    if (level !== null && result.agentId !== undefined) {
      const id = result.agentId
      await update($, agentLevels, m => ({ ...m, [id]: level }))
      if (!s.quiet) $.ui.toast(WORDS[s.l].subagent(e.description, level))
      await log($, s, { event: 'subagent', type: e.subagentType, level })
    }
    return result
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
    const c = await read($, card)
    if ((o === null && c === null) || e.props.hasSurvey) return next(e)
    const w = WORDS[s.l]
    // Working: "1: Switch to high". After the turn: "[ Switch to high ]", no digit.
    const look = (d: string) => (e.props.isWorking ? { hotkey: d, plain: true as const } : {})
    const ui = $.ui.resolve(e)
    const { Box, Text, Button } = ui
    const current = o?.from ?? c?.current ?? ''
    const rec = o?.level ?? c?.rec ?? null
    const gauge =
      e.surface !== 'terminal' && 'Svg' in ui && ui.Svg ? (
        <ui.Svg key="gauge" source={gaugeSvg(current, rec)} alt={`effort ${current}`} width={34} height={16} isInteractive />
      ) : (
        <Text key="gauge">
          {gaugeText(current, rec).map(g => (
            <Text color={g.role === 'off' ? undefined : '#D97757'} dimColor={g.role === 'off'} bold={g.role === 'on'}>
              {g.bar}
            </Text>
          ))}
        </Text>
      )
    const share = c?.share !== undefined && !o ? ` (${c.share.toFixed(2)})` : ''
    const words = (o ? (o.turnId !== undefined ? w.midBand(o) : w.band(o)) : c ? w.cardLine(c) : '') + share
    const facts = await bandFacts($, s, e.props.bodyColumns)
    return (
      <Box flexDirection="row">
        {gauge}
        <Text>  {words}  </Text>
        {facts.length > 0 ? <Text dimColor>│ {facts.join(' · ')}  </Text> : null}
        {o ? <Button key="switch" {...look('1')} label={w.switchTo(o.level)} onPress={() => acceptOffer($, o, s)} /> : null}
        {o ? <Text>  </Text> : null}
        {o ? <Button key="keep" {...look('2')} label={w.keep(o.from)} onPress={() => declineOffer($, o, s)} /> : null}
        {o ? <Text>  </Text> : null}
        {o ? null : <Button key="ledger" label={w.ledger} onPress={() => openLedger($, s)} />}
        {o ? null : <Text>  </Text>}
        <Button key="close" {...(o ? look('0') : {})} role="dismiss" label={w.close} onPress={() => closeOffer($)} />
      </Box>
    )
  })

  // The ledger: what each level cost, and what following Jev would have changed.
  on('ui.render', { component: 'Pane', requestId: LEDGER_PANE }, async ($, e) => {
    await read($, ledgerTick) // redraw when a turn is added
    const w = WORDS[s.l]
    const ui = $.ui.resolve(e)
    const { Box, Text } = ui
    const sum = summary(await readLedger($), await readJevDays($), await $.clock.now())
    if (sum.rows.length === 0 && sum.weekCalls === 0) return <Text dimColor>{w.ledgerEmpty}</Text>
    return (
      <Box flexDirection="column">
        <Text bold color="#D97757">
          {w.ledgerHead(usd(sum.todayUsd), usd(sum.weekUsd), sum.weekCalls)}
        </Text>
        {e.surface !== 'terminal' && 'Svg' in ui && ui.Svg ? (
          <ui.Svg key="chart" source={ledgerSvg(sum.rows)} alt="turns per effort level" isInteractive />
        ) : null}
        {sum.rows.map(r => (
          <Text>{w.ledgerRow(r.level, r.turns)}</Text>
        ))}
        <Text dimColor>{w.ledgerJev(sum.judged, sum.followed)}</Text>
      </Box>
    )
  })
}

// ------------------------------------------------------------- judging

/**
 * Judge a typed message and leave the answer for the next model request.
 * Returns what to attach to the prompt: the person's answers to a spec
 * interview, when the message hands over a long run with open questions.
 */
async function judge($: EngineInterface, text: string, s: Settings, order: { latest: number }): Promise<string[]> {
  const mine = (order.latest += 1)
  const isStale = () => order.latest !== mine
  await update($, offer, () => null) // a new message replaces an unanswered offer
  const t = await $.clock.now()
  if (!s.key) {
    await update($, pending, () => null)
    if (!(await read($, warnedNoKey))) {
      await update($, warnedNoKey, () => true)
      $.ui.toast(WORDS[s.l].noKey)
    }
    return []
  }
  try {
    const messages = await $.session.messages()
    const rows = Array.isArray(messages) ? messages : []
    const recent = recentTurns(rows)
    if (isGoAhead(text)) {
      const level = await sizeGoAhead($, rows, text)
      if (isStale()) return []
      await update($, pending, () => ({ answers: level ? certain(level) : null, isGoAhead: true, t }))
      await log($, s, { event: 'prompt', goAhead: 'exact', sized: level, message_chars: text.length })
      return []
    }
    let answers: Answers | null = await askJev($, s.key, jevBody(text, recent))
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
    if (isStale()) return []
    await update($, pending, () => ({ answers, isGoAhead: goAhead, t }))
    if (s.interview && answers !== null && answers.handoff_ambiguous.noul >= AMBIGUITY_MIN) {
      return await interview($, text, recent, s)
    }
    return []
  } catch (err) {
    const status = err instanceof HttpStatus ? err.status : undefined
    const failure: Pending['failure'] = status === 401 || status === 403 ? 'badKey' : 'error'
    if (!isStale()) await update($, pending, () => ({ answers: null, isGoAhead: false, failure, t }))
    // The kind of failure only: a parser's message can quote the response.
    await log($, s, { event: 'error', error: err instanceof Error ? err.name : 'unknown', status })
    return []
  }
}

async function askJev($: EngineInterface, key: string, body: unknown): Promise<Answers> {
  const response = await jevCall($, key, body)
  return checked(response.answers)
}

/** One request to Jev; its JSON body, or a throw. */
async function jevCall($: EngineInterface, key: string, body: unknown): Promise<{ answers?: unknown }> {
  const response = await within(
    $,
    TIMEOUT_MS,
    $.http.fetch(JEV_URL, {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
  if (!response.ok) throw new HttpStatus(response.status)
  const parsed = JSON.parse(response.text) as { answers?: unknown; usage?: { input_tokens?: unknown; output_tokens?: unknown } }
  await countJev($, parsed.usage)
  return parsed
}

/** Jev's usage as its answer reports it, added to today's count. */
async function countJev($: EngineInterface, used: { input_tokens?: unknown; output_tokens?: unknown } | undefined) {
  const input = typeof used?.input_tokens === 'number' ? used.input_tokens : 0
  const output = typeof used?.output_tokens === 'number' ? used.output_tokens : 0
  try {
    await $.store.set('jev', counted(await readJevDays($), await $.clock.now(), input, output))
    await update($, ledgerTick, n => n + 1)
  } catch {
    // Uncounted is fine.
  }
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

/** A subagent's task, sized by Jev on its own words; null when Jev isn't sure. */
async function sizeTask($: EngineInterface, task: string, s: Settings): Promise<Level | null> {
  try {
    return subagentLevel(await askJev($, s.key, jevBody(task, [])))
  } catch {
    return null
  }
}

/**
 * Two or three questions about what the long run leaves open, drafted by the
 * small model from the message (standard ones if it can't), asked one by one.
 * The answers go to Claude with the prompt; they are never logged.
 */
async function interview($: EngineInterface, text: string, recent: readonly Turn[], s: Settings): Promise<string[]> {
  const w = WORDS[s.l]
  const questions = await draftQuestions($, text, recent, s)
  const answered: string[] = []
  for (const q of questions) {
    let a: string
    try {
      a = await $.ui.ask(q, { options: [w.leaveIt, w.skipRest], header: w.specHeader })
    } catch {
      break // dismissed, or nobody to ask (-p)
    }
    if (a === w.skipRest) break
    if (a !== w.leaveIt && a.trim() !== '') answered.push(`Q: ${q}\nA: ${a.trim()}`)
  }
  await log($, s, { event: 'interview', asked: questions.length, answered: answered.length })
  return answered.length > 0 ? [`${w.specIntro}\n\n${answered.join('\n\n')}`] : []
}

async function draftQuestions($: EngineInterface, text: string, recent: readonly Turn[], s: Settings): Promise<string[]> {
  const fallback = [...WORDS[s.l].specFallback]
  try {
    const convo = recent.map(t => `[${t.role}] ${t.text.slice(-800)}`).join('\n')
    const result = await within(
      $,
      SPEC_TIMEOUT_MS,
      $.model.complete({
        model: 'haiku',
        maxTokens: 300,
        system:
          'You help a person hand a long autonomous task to a coding agent. Write the 3 questions whose answers ' +
          'would most change how the agent does the task: success criteria, scope, constraints. One per line, ' +
          'no numbering, each under 20 words, in the language of the request.',
        prompt: `Recent conversation:\n${convo}\n\nThe request:\n${text.slice(0, 4000)}`,
      }),
    )
    if (!result.isAnswered) return fallback
    const lines = result.text
      .split('\n')
      .map(l => l.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '').trim())
      .filter(l => l.length > 8 && l.endsWith('?'))
    return lines.length >= 2 ? lines.slice(0, 3) : fallback
  } catch {
    return fallback
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
  let ov = await read($, override)
  if (ov !== null && ov.base === null) {
    // A switch pressed in the band starts from the setting this request carries.
    const start: Override | null = ov.level === setting ? null : { ...ov, base: setting }
    await update($, override, () => start)
    ov = start
  }
  // The person changed the setting themselves: theirs wins.
  if (ov !== null && ov.base !== setting) await release($, s, setting)
  const level = ov !== null && ov.base === setting ? ov.level : setting
  if ((await read($, lastLevel)) !== level && ov?.turnId === undefined) {
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
  let drawn: Card | null = null
  if (p.failure !== undefined) {
    line = p.failure === 'badKey' ? w.badKey : w.error
    isNews = p.failure === 'badKey'
  } else if (p.answers === null) {
    line = p.isGoAhead ? w.goAhead : w.unclear
  } else {
    const mins = switchMins(await readTally($), s.selfTune)
    ;[line, chosen, isNews] = await weigh($, p.answers, p.isGoAhead, setting, level, mins, s)
    const v = verdict(p.answers, chosen, mins)
    drawn = { current: chosen, rec: v.level, kind: v.kind, share: v.share }
    const named = verdict(p.answers, null).level
    await update($, turn, t => (t === null ? t : { ...t, rec: named }))
  }
  const prefix = chosen !== setting ? w.sending(chosen, setting) + ' ' : ''
  // A status line stays until replaced: one quiet doesn't show is cleared, not left stale.
  // What actually runs comes first, so a truncated line still says it.
  const shown = !s.quiet || isNews || prefix !== ''
  $.ui.status(shown ? prefix + line : undefined)
  await update($, card, () => (shown ? drawn : null))
  return chosen
}

/** Jev's answer against the level: the line, the level to send, and whether it is news. */
async function weigh(
  $: EngineInterface,
  answers: Answers,
  isGoAhead: boolean,
  setting: string,
  level: string,
  mins: { up: number; down: number },
  s: Settings,
): Promise<[string, string, boolean]> {
  const w = WORDS[s.l]
  const v: Verdict = { ...verdict(answers, level, mins), sized: isGoAhead }
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
      if (answer === 'switch' || answer === 'keep') await tally($, dir, answer === 'switch')
    } else {
      await update($, offer, () => ({ direction: dir, level: target, from: level, setting, share: v.share }))
      answer = 'offered'
    }
  }
  await log($, s, {
    event: 'decision', kind: v.kind, rec: v.level, share: round(v.share), setting, level, chosen,
    answer, goAhead: isGoAhead, ask_first: s.askFirst, mins,
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
  // Not from o.setting: the person may have moved the setting since the offer.
  await update($, override, () => ({ level: o.level, base: null, ...(o.turnId !== undefined ? { turnId: o.turnId } : {}) }))
  await update($, offer, () => null)
  $.ui.status(WORDS[s.l].switched(o.level))
  if (o.turnId === undefined) await tally($, o.direction, true)
  await log($, s, { event: 'offer', answer: 'switch', rec: o.level, from: o.from, setting: o.setting, midturn: o.turnId !== undefined })
}

async function declineOffer($: EngineInterface, o: Offer, s: Settings) {
  if (o.turnId === undefined) {
    await update($, declined, d => ({ ...d, [o.direction]: o.from }))
    await tally($, o.direction, false)
  }
  await update($, offer, () => null)
  await log($, s, { event: 'offer', answer: 'keep', rec: o.level, from: o.from, setting: o.setting, midturn: o.turnId !== undefined })
}

async function closeOffer($: EngineInterface) {
  await update($, offer, () => null)
  await update($, card, () => null)
}

// ------------------------------------------------------------- the turn

/** The first main-loop request of a turn opens its ledger note. */
async function openTurn($: EngineInterface, turnId: string, index: number) {
  const note = await read($, turn)
  if (note !== null && note.turnId === turnId) return
  if (note !== null && index > 0) return // a note for another turn still open: leave it to its turn.complete
  const begun = await read($, started)
  const task = begun !== null && begun.turnId === turnId ? begun.text : ''
  await update($, turn, () => ({ turnId, task, rec: null, level: null, steps: [], isChecked: false }))
}

async function noteStep($: EngineInterface, turnId: string, level: string | null, said: string, tools: string[]) {
  await update($, turn, t =>
    t === null || t.turnId !== turnId
      ? t
      : { ...t, level: level ?? t.level, steps: [...t.steps, { tools, said: said.slice(-300) }].slice(-6) },
  )
}

/** The turn ended: one ledger row, and a switch made for this turn alone ends with it. */
async function closeTurn($: EngineInterface, turnId: string) {
  const note = await read($, turn)
  const ov = await read($, override)
  if (ov !== null && ov.turnId === turnId) await update($, override, () => null)
  await update($, offer, o => (o !== null && o.turnId === turnId ? null : o))
  if (note === null || note.turnId !== turnId) return
  await update($, turn, () => null)
  if (note.level === null) return
  const row: LedgerTurn = { t: await $.clock.now(), level: note.level, rec: note.rec }
  try {
    await $.store.set('ledger', added(await readLedger($), row))
    await update($, ledgerTick, n => n + 1)
  } catch {
    // A ledger that can't be kept never gets in the way.
  }
}

/**
 * Once per long turn on high or max: if the rest looks mechanical, offer
 * low for the rest of this turn, in the band (never a dialog mid-turn).
 */
async function midTurnCheck($: EngineInterface, turnId: string, index: number, level: string, setting: string, s: Settings) {
  if (!s.midturn || !s.key || index < MID_TURN_STEP || (level !== 'high' && level !== 'max' && level !== 'xhigh')) return
  const note = await read($, turn)
  if (note === null || note.turnId !== turnId || note.isChecked || (await read($, offer)) !== null) return
  await update($, turn, t => (t === null ? t : { ...t, isChecked: true }))
  try {
    const body = await jevCall($, s.key, midTurnBody(note.task, note.steps))
    const answers = body.answers as { rest_is_mechanical?: { noul?: unknown } } | undefined
    const p = answers?.rest_is_mechanical?.noul
    await log($, s, { event: 'midturn', level, mechanical: typeof p === 'number' ? round(p) : null, step: index })
    if (typeof p !== 'number' || p < MID_TURN_MIN) return
    const hint: Offer = { direction: 'down', level: 'low', from: level, setting, share: p, turnId }
    await update($, offer, () => hint)
  } catch {
    // No hint this time.
  }
}

/**
 * The band's side facts, as room allows: what Jev cost today, from the usage
 * its answers report, and the levels subagents got. Claude's own spending
 * is not this plugin's to show.
 */
async function bandFacts($: EngineInterface, s: Settings, columns: number): Promise<string[]> {
  const w = WORDS[s.l]
  const facts: string[] = []
  if (columns >= 70) {
    const sum = summary([], await readJevDays($), await $.clock.now())
    if (sum.todayCalls > 0) facts.push(w.jevCost(usd(sum.todayUsd)))
  }
  const subs = Object.values(await read($, agentLevels))
  if (columns >= 100 && subs.length > 0) {
    const counts = LEVELS.map(lv => [lv, subs.filter(x => x === lv).length] as const).filter(([, n]) => n > 0)
    facts.push(w.subagents(counts.map(([lv, n]) => (n > 1 ? `${n}×${lv}` : lv)).join(' ')))
  }
  return facts
}

/** A subagent's first request before its spawn returned: it takes the oldest sized spawn not yet taken. */
async function claimSpawn($: EngineInterface, agentId: string): Promise<string | undefined> {
  const free = (await read($, spawning)).find(x => x.agentId === null)
  if (free === undefined) return undefined
  await update($, spawning, list => list.map(x => (x.id === free.id ? { ...x, agentId } : x)))
  await update($, agentLevels, m => ({ ...m, [agentId]: free.level }))
  return free.level
}


// ------------------------------------------------------------- what lasts across sessions

async function readLedger($: EngineInterface): Promise<LedgerTurn[]> {
  try {
    const value = await $.store.get('ledger')
    return Array.isArray(value) ? (value as LedgerTurn[]) : []
  } catch {
    return []
  }
}

async function readJevDays($: EngineInterface): Promise<JevDay[]> {
  try {
    const value = await $.store.get('jev')
    return Array.isArray(value) ? (value as JevDay[]) : []
  } catch {
    return []
  }
}

async function readTally($: EngineInterface): Promise<Tally | null> {
  try {
    return ((await $.store.get('tally')) as Tally | undefined) ?? null
  } catch {
    return null
  }
}

async function tally($: EngineInterface, dir: 'up' | 'down', isTaken: boolean) {
  try {
    await $.store.set('tally', tallied(await readTally($), dir, isTaken))
  } catch {
    // Untuned is fine.
  }
}

async function openLedger($: EngineInterface, s: Settings) {
  await $.ui.open({ id: LEDGER_PANE, title: WORDS[s.l].ledgerTitle })
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
    // A log that exists but can't be read (over the 4 MiB read limit, say) is
    // left alone: the read throws and nothing is written over it.
    const old = (await $.fs.exists(path)) ? await $.fs.read(path) : ''
    if (old.length > LOG_MAX_CHARS) {
      await $.fs.write(`${dir}/decisions.1.jsonl`, old)
    }
    const line = { t: await $.clock.now(), session: await $.session.id(), version: VERSION, mod: true, ...record }
    await $.fs.write(path, (old.length > LOG_MAX_CHARS ? '' : old) + JSON.stringify(line) + '\n')
  } catch {
    // A log that can't be written never gets in the way.
  }
}
