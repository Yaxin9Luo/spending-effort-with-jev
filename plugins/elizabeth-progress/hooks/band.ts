// The band's picture: one SVG at 100% width and 1:1 pixels, a fixed height,
// every horizontal position a percentage so it fits any window width.
// Left: Elizabeth standing on the progress bar. Right: a row of compact figures.
import type { Ctx, Limit, Part } from '../types'
import { elizabeth } from './elizabeth'
import type { Mood } from './elizabeth'

export const H = 84
const L0 = 1.6
const L1 = 53
const R0 = 56
const R1 = 99.4
const TY = 54
const SCALE = 0.4
const PALETTE = ['#5b8def', '#e07a5f', '#3d9a8b', '#e0a43c', '#8c7ae6', '#9aa0a6']

export const k = (n: number) =>
  n >= 1e6 ? `${(n / 1e6).toFixed(2).replace(/\.?0+$/, '')}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`
export const tone = (r: number) => (r < 0.6 ? '#5b8def' : r < 0.85 ? '#e0a43c' : '#d4523c')
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
const until = (iso: string | undefined, now: number) => {
  if (!iso) return ''
  const m = Math.max(0, Math.round((Date.parse(iso) - now) / 60000))
  return m >= 1440 ? `${Math.floor(m / 1440)}d ${Math.floor((m % 1440) / 60)}h` : m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m`
}
const LIMIT_NAME: Record<string, string> = { five_hour: '5h limit', seven_day: 'Weekly', spend_limit: 'Spend' }

const STYLE = `<style>
  html,body{margin:0;padding:0;overflow:hidden;background:transparent}
  text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
  .t{fill:#2a2a2a}.m{fill:#8b8780}.trk{fill:#e2dfd8}.div{stroke:#dcd8d0}.panel{fill:#fff;fill-opacity:.62}
  @media (max-width: 900px){.wide,.only-wide{display:none}}
  @media (min-width: 901px){.only-narrow{display:none}}
  @media (prefers-color-scheme: dark){.t{fill:#ece9e2}.m{fill:#9b978f}.trk{fill:#3a3835}.div{stroke:#45423e}.panel{fill:#3a3835;fill-opacity:.55}}
</style>`

export type View = { c: Ctx; ps: Part[]; ls: Limit[]; usd: number | null; h: number[]; at: number | null; now: number }

export const svg = ({ c, ps, ls, usd, h, at, now }: View) => {
  const p = Math.min(100, c.percent)
  const span = L1 - L0
  const px = (v: number) => L0 + (Math.min(100, v) / 100) * span
  const pc = (v: number) => `${v.toFixed(3)}%`
  const ratio = p / (at ?? 100)
  const out: string[] = [STYLE]

  // Two light panels hold the left and right halves.
  out.push(`<rect class="panel" x="0.3%" y="4" width="${pc(L1 + 1.4)}" height="${H - 8}" rx="12"/>`)
  out.push(`<rect class="panel" x="${pc(R0 - 0.9)}" y="4" width="${pc(R1 - R0 + 1.2)}" height="${H - 8}" rx="12"/>`)

  // The bar: the track, the used part coloured by category, the auto-compact zone
  // (hatched), and ticks at 25/50/75.
  out.push(`<defs><clipPath id="trk"><rect x="${pc(L0)}" y="${TY}" width="${pc(span)}" height="7" rx="3.5"/></clipPath>
    <pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="#d4523c" fill-opacity="0.08"/><line x1="0" y1="0" x2="0" y2="5" stroke="#d4523c" stroke-opacity="0.4" stroke-width="1.6"/></pattern></defs>`)
  const g: string[] = [`<rect class="trk" x="${pc(L0)}" y="${TY}" width="${pc(span)}" height="7"/>`]
  if (at !== null && at < 100) g.push(`<rect x="${pc(px(at))}" y="${TY}" width="${pc(L1 - px(at))}" height="7" fill="url(#hatch)"/>`)
  const sum = ps.reduce((a, r) => a + r.tokens, 0)
  if (sum > 0) {
    let x = L0
    ps.forEach((r, i) => {
      const w = (r.tokens / sum) * (px(p) - L0)
      g.push(`<rect x="${pc(x)}" y="${TY}" width="${pc(w + 0.05)}" height="7" fill="${PALETTE[i % PALETTE.length]}"/>`)
      x += w
    })
  } else {
    g.push(`<rect x="${pc(L0)}" y="${TY}" width="${pc(px(p) - L0)}" height="7" fill="${tone(ratio)}"/>`)
  }
  for (const t of [25, 50, 75]) g.push(`<rect x="${pc(px(t))}" y="${TY}" width="1.2" height="7" fill="#fff" fill-opacity="0.65"/>`)
  out.push(`<g clip-path="url(#trk)">${g.join('')}</g>`)
  // Steps aside as Elizabeth comes near, so the two never overlap.
  if (at !== null && at < 100 && p < at - 22) {
    out.push(`<text class="m" x="${pc(L1)}" y="${TY - 7}" font-size="10" text-anchor="end">auto-compact ${Math.round(at)}%</text>`)
  }

  // The legend: one line under the bar; a narrow window keeps the first three.
  const lg: string[] = []
  let lx = 0
  ps.forEach((r, i) => {
    const name = r.name.replace(/^System /, 'Sys ')
    lg.push(`<g${i >= 3 ? ' class="wide"' : ''}><circle cx="${lx + 3}" cy="${TY + 18.5}" r="3" fill="${PALETTE[i % PALETTE.length]}"/>
      <text x="${lx + 10}" y="${TY + 22}" font-size="10.5"><tspan class="m">${esc(name)} </tspan><tspan class="t" font-weight="600">${k(r.tokens)}</tspan></text></g>`)
    lx += 22 + (name.length + 1 + k(r.tokens).length) * 5.6
  })
  out.push(`<svg x="${pc(L0)}" y="0" overflow="visible">${lg.join('')}</svg>`)

  // Elizabeth stands on the top edge of the bar and walks with the usage.
  const mood: Mood = ratio >= 0.95 ? 'crying' : ratio >= 0.8 ? 'angry' : 'calm'
  const ex = Math.min(L1 - 3.2, Math.max(L0 + 2.6, px(p)))
  out.push(`<svg x="${pc(ex)}" y="0" overflow="visible"><g transform="translate(0 ${TY - 1.5}) scale(${SCALE})">${elizabeth({ sign: `${c.percent}%`, mood, lw: 2.2, signSize: 20 })}</g></svg>`)

  // The row of figures on the right.
  const deltas = h.slice(1).map((v, i) => v - (h[i] ?? v)).filter(d => d > 0)
  const recent = deltas.slice(-5)
  const avg = recent.length ? recent.reduce((a, b) => a + b, 0) / recent.length : 0
  const room = (at ?? 100) - p
  type Col = { label: string; value: string; sub: string; frac?: number; spark?: number[] }
  const cols: Col[] = [
    { label: 'Context', value: k(c.tokens), sub: `${c.percent}% of ${k(c.window)}`, frac: ratio },
    {
      label: 'Turns left',
      value: avg > 0 ? (room / avg < 1 ? (room > 0 ? '<1' : '0') : `≈${Math.floor(room / avg)}`) : '—',
      sub: avg > 0 ? `+${avg.toFixed(1)}%/turn` : 'need 2 turns',
      spark: h.slice(-24),
    },
    ...ls.slice(0, 2).map(l => ({
      label: LIMIT_NAME[l.kind] ?? l.kind,
      value: `${l.percentUsed}%`,
      sub: l.resetsAt ? `resets ${until(l.resetsAt, now)}` : '',
      frac: l.percentUsed / 100,
    })),
    ...(usd !== null ? [{ label: 'Cost', value: `$${usd.toFixed(2)}`, sub: 'this session' }] : []),
  ]
  const drawCols = (list: Col[], cls: string) => {
    const g: string[] = []
    const cw = (R1 - R0) / list.length
    list.forEach((col, i) => {
      const x0 = R0 + i * cw
      const x = x0 + (i ? 1.3 : 0.6)
      const inner = cw - (i ? 2.6 : 1.9)
      if (i) g.push(`<line class="div" x1="${pc(x0)}" y1="16" x2="${pc(x0)}" y2="${H - 16}"/>`)
      const hot = col.frac !== undefined && col.frac >= 0.85
      g.push(`<text class="m" x="${pc(x)}" y="23" font-size="9.5" font-weight="500" letter-spacing="0.5">${esc(col.label.toUpperCase())}</text>`)
      g.push(`<text ${hot ? `fill="${tone(col.frac ?? 0)}"` : 'class="t"'} x="${pc(x)}" y="45" font-size="19" font-weight="600" letter-spacing="-0.2">${esc(col.value)}</text>`)
      g.push(`<text class="m" x="${pc(x)}" y="60" font-size="10.5">${esc(col.sub)}</text>`)
      if (col.frac !== undefined) {
        g.push(`<rect class="trk" x="${pc(x)}" y="66" width="${pc(inner)}" height="3" rx="1.5"/>`)
        g.push(`<rect x="${pc(x)}" y="66" width="${pc(inner * Math.min(1, col.frac))}" height="3" rx="1.5" fill="${tone(col.frac)}"/>`)
      }
      if (col.spark && col.spark.length > 1) {
        const sp = col.spark
        const top = Math.max(...sp, 1)
        const pts = sp.map((v, j) => `${((j / (sp.length - 1)) * 100).toFixed(1)},${(10 - (v / top) * 9).toFixed(1)}`).join(' ')
        g.push(`<svg x="${pc(x)}" y="61" width="${pc(inner)}" height="10" viewBox="0 0 100 10" preserveAspectRatio="none" overflow="visible"><polyline points="${pts}" fill="none" stroke="#5b8def" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`)
      }
    })
    return `<g class="${cls}">${g.join('')}</g>`
  }
  out.push(drawCols(cols, 'only-wide'))
  out.push(drawCols(cols.filter(col => col.label !== 'Cost'), 'only-narrow'))

  return `<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="${H}">${out.join('')}</svg>`
}
