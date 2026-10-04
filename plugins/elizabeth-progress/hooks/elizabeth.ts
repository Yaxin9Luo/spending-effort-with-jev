// Elizabeth (Gintama), drawn by hand from a front-view acrylic stand and
// screenshots of the anime, with two-step cel shading. Unofficial fan art.
// Coordinates: the origin is between the feet; the top of the head is at
// y=-111, the hem at y≈-11; the body is about 62 wide.
// The sign: the hand on the right of the picture holds up a white stick, the
// board above it to the right, behind the head.

export type Mood = 'calm' | 'angry' | 'crying'

export type ElizabethOptions = {
  sign: string
  mood?: Mood
  /** Line width, in the character's units; raise it when drawn small so lines stay about 1px on screen. */
  lw?: number
  animate?: boolean
  /** Font size on the sign, in the character's units; raise it when drawn small so it stays legible. */
  signSize?: number
}

const OUT = '#4a4a4a'
const SHADE = '#e1e5ec'
const SHADE_DEEP = '#d3d8e0'
const BEAK_LINE = '#6a4b1a'
const TOE_LINE = '#8a5f17'
const SIGN_FONT = `'Marker Felt', 'Chalkboard SE', 'Comic Sans MS', sans-serif`

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;')

const DEFS = `<defs>
  <linearGradient id="eliz-toe" x1="0" y1="-16" x2="0" y2="4" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#f6c24c"/><stop offset="0.6" stop-color="#eba636"/><stop offset="1" stop-color="#d4891f"/>
  </linearGradient>
  <linearGradient id="eliz-beak-top" x1="0" y1="-88.4" x2="0" y2="-79.2" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#f9cf63"/><stop offset="1" stop-color="#f1b33c"/>
  </linearGradient>
  <linearGradient id="eliz-beak-low" x1="0" y1="-80.6" x2="0" y2="-73.8" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#eda93b"/><stop offset="1" stop-color="#d68c26"/>
  </linearGradient>
</defs>`

// An eye: a slightly tall circle, a small black dot in the middle, three lashes flicked outward on top.
const eye = (cx: number, cy: number, lw: number) => {
  const rx = 5.9
  const ry = 6.3
  const lashes = [-122, -90, -58]
    .map(d => {
      const t = (d * Math.PI) / 180
      const x1 = cx + rx * Math.cos(t)
      const y1 = cy + ry * Math.sin(t)
      const tilt = t + (d + 90) * 0.006
      return `M${x1.toFixed(2)} ${y1.toFixed(2)} l${(2.4 * Math.cos(tilt)).toFixed(2)} ${(2.4 * Math.sin(tilt)).toFixed(2)}`
    })
    .join(' ')
  return `<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="#fff" stroke="${OUT}" stroke-width="${lw * 0.8}"/>
<circle cx="${cx}" cy="${cy + 0.2}" r="0.75" fill="#151515"/>
<path d="${lashes}" stroke="${OUT}" stroke-width="${lw * 0.7}" stroke-linecap="round" fill="none"/>`
}

// A toe: a plump ellipse from the heel (bx,by) to the tip (tx,ty), as ellipse attributes.
const toe = (bx: number, by: number, tx: number, ty: number, w: number) => {
  const len = Math.hypot(bx - tx, by - ty)
  const ang = (Math.atan2(by - ty, bx - tx) * 180) / Math.PI
  const cx = ((bx + tx) / 2).toFixed(2)
  const cy = ((by + ty) / 2).toFixed(2)
  return `cx="${cx}" cy="${cy}" rx="${(len / 2).toFixed(2)}" ry="${w / 2}" transform="rotate(${ang.toFixed(1)} ${cx} ${cy})"`
}

const TOES = [toe(-16, -12.8, -39.6, -6.8, 7.8), toe(-15, -10.2, -36.6, 0.6, 8.2), toe(-13.6, -7.6, -28.8, 3.4, 7.8)]
const WEB = 'M-11 -14.4 L-37 -8.6 L-35 -0.4 L-28 3 C-20 1.6,-13.4 -0.6,-10.4 -4 C-8.8 -7,-9 -11,-11 -14.4 Z'

// The left foot (on the left of the picture): a big webbed fan with three round toes
// spread down and to the left. The right foot is its mirror image.
const foot = (mirror: boolean, lw: number) => {
  const parts = (attrs: string) =>
    `<path d="${WEB}" ${attrs}/>` + TOES.map(t => `<ellipse ${t} ${attrs}/>`).join('')
  return `<g${mirror ? ' transform="scale(-1 1)"' : ''}>
  ${parts(`fill="${TOE_LINE}" stroke="${TOE_LINE}" stroke-width="${lw * 1.5}" stroke-linejoin="round"`)}
  ${parts('fill="url(#eliz-toe)"')}
  <path d="M-33.2 -3.2 C-30 -5,-26.6 -6.6,-23 -7.6 M-28 0.6 C-25.4 -1.8,-22.6 -3.6,-19.6 -4.8" stroke="#c27c1e" stroke-width="${lw * 0.7}" fill="none" stroke-linecap="round" opacity="0.75"/>
  <path d="M-36.6 -9.4 C-31 -11.4,-24 -12.8,-18 -13.4" stroke="#fbd877" stroke-width="${lw * 1.4}" fill="none" stroke-linecap="round" opacity="0.9"/>
  <path d="M-34.6 -2.6 C-29.6 -5.2,-24.6 -7,-19.6 -8.2" stroke="#fbd877" stroke-width="${lw * 1.2}" fill="none" stroke-linecap="round" opacity="0.7"/>
</g>`
}

// 💢 the anger mark: four arcs curling toward the centre.
const anger = (cx: number, cy: number, s: number, lw: number, color: string) => {
  const q = (sx: number, sy: number) =>
    `M${cx + sx * s} ${cy + sy * s * 0.28} Q${cx + sx * s * 0.28} ${cy + sy * s * 0.28} ${cx + sx * s * 0.28} ${cy + sy * s}`
  return `<path d="${q(-1, -1)} ${q(1, -1)} ${q(-1, 1)} ${q(1, 1)}" stroke="${color}" stroke-width="${lw * 1.6}" fill="none" stroke-linecap="round"/>`
}

// The beak: a lemon shape pointed at both ends. The upper half is bright yellow,
// larger, with a highlight; the lower half is more orange and darker toward the
// bottom; a shadow at the right end gives it thickness.
const beak = (lw: number) => {
  const top = 'M-14 -80.6 C-12.6 -86.4,-5.6 -88.6,1 -88.4 C8 -88.2,13.8 -85.6,14.2 -81'
  const lipFwd = 'M-14 -80.6 C-9 -80.4,-3 -78.8,2 -79.2 C7 -79.6,11 -80.8,14.2 -81'
  const lipBack = 'C11 -80.8,7 -79.6,2 -79.2 C-3 -78.8,-9 -80.4,-14 -80.6'
  const bottom = 'C13.4 -76.2,8 -74.2,0.6 -74.2 C-6.4 -74.2,-11.8 -76.4,-14 -80.6'
  return `<g transform="translate(0 1.4)">
  <clipPath id="eliz-beak"><path d="${top} ${bottom} Z"/></clipPath>
  <path d="M-9 -73.2 C-4 -71.4,5 -71.4,10 -73.2 C6 -72,-4 -72,-9 -73.2 Z" fill="${SHADE_DEEP}"/>
  <ellipse cx="0.6" cy="-72.6" rx="9.6" ry="1.5" fill="${SHADE_DEEP}" opacity="0.6"/>
  <g clip-path="url(#eliz-beak)">
    <path d="${lipFwd} ${bottom} Z" fill="url(#eliz-beak-low)"/>
    <path d="M15 -84 C15 -78,12 -74.6,7 -73.4 L16 -72 Z" fill="#c47b1c" opacity="0.5"/>
    <path d="M-12 -76.6 C-7 -74.6,1 -74.4,7 -75.4" stroke="#c47b1c" stroke-width="${lw * 0.7}" fill="none" stroke-linecap="round" opacity="0.45"/>
    <path d="${top} ${lipBack} Z" fill="url(#eliz-beak-top)"/>
    <path d="M-4 -86.6 C1 -87.6,7 -87.2,10.6 -85.4 C6.6 -85,1.4 -85.2,-4 -86.6 Z" fill="#fde7a6" opacity="0.9"/>
    <path d="M-14.4 -80 C-13 -84,-10 -86.4,-6.4 -87.4" stroke="#dc9d2e" stroke-width="${lw * 0.8}" fill="none" stroke-linecap="round" opacity="0.55"/>
    <path d="M14.6 -82.6 C14 -80.6,13.2 -80,12 -79.6" stroke="#c47b1c" stroke-width="${lw * 0.8}" fill="none" opacity="0.6"/>
  </g>
  <path d="${lipFwd}" stroke="${BEAK_LINE}" stroke-width="${lw * 0.65}" fill="none" stroke-linecap="round"/>
  <path d="${top} ${bottom} Z" fill="none" stroke="${BEAK_LINE}" stroke-width="${lw * 0.75}" stroke-linejoin="round"/>
</g>`
}

const BODY =
  'M-27 -11 C-30.5 -14,-31.5 -24,-31.2 -36 C-30.8 -52,-29.4 -72,-28.4 -86 C-27.2 -102,-15.6 -111,0 -111 C15.6 -111,27.2 -102,28.4 -86 C29.4 -72,30.8 -52,31.2 -36 C31.5 -24,30.5 -14,27 -11 C20 -8.6,9 -9.6,4 -13.4 C2.4 -14.6,1.2 -15.2,0 -15.2 C-1.2 -15.2,-2.4 -14.6,-4 -13.4 C-9 -9.6,-20 -8.6,-27 -11 Z'

export const elizabeth = ({ sign, mood = 'calm', lw = 1, animate = true, signSize = 14 }: ElizabethOptions) => {
  const bob = animate
    ? '<animateTransform attributeName="transform" type="translate" values="0 0;0 -1.6;0 0" dur="1.6s" repeatCount="indefinite"/>'
    : ''
  const sway = animate
    ? '<animateTransform attributeName="transform" type="rotate" values="-2.5 30 -66;2.5 30 -66;-2.5 30 -66" dur="2.6s" repeatCount="indefinite"/>'
    : ''

  // The sign: when angry it alternates between the percentage and 💢.
  const text = `<text x="45" y="${-116.8 + signSize * 0.36}" font-size="${signSize}" font-weight="700" text-anchor="middle" fill="#1d1d1d" font-family="${SIGN_FONT}">${esc(sign)}</text>`
  const signFace =
    mood === 'calm' || !animate
      ? text + (mood === 'calm' ? '' : anger(66, -127, 3.2, lw, '#c8402d'))
      : `<g>${text}<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;0.55;0.6;0.95;1" dur="3.2s" repeatCount="indefinite"/></g>
<g opacity="0">${anger(45, -116.8, 7, lw, '#c8402d')}<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;0.55;0.6;0.95;1" dur="3.2s" repeatCount="indefinite"/></g>`

  const tears =
    mood === 'crying'
      ? `<path d="M-15.4 -86.6 c-2.6 0.4,-3.4 3,-1.2 3.6 c1.6 0.4,3 -0.6,3.2 -2 c0.2 -1.2,-0.8 -1.8,-2 -1.6 Z" fill="#a9c8f0" opacity="0.9"/>
<path d="M15.4 -86.6 c2.6 0.4,3.4 3,1.2 3.6 c-1.6 0.4,-3 -0.6,-3.2 -2 c-0.2 -1.2,0.8 -1.8,2 -1.6 Z" fill="#a9c8f0" opacity="0.9"/>`
      : ''

  return `<g class="elizabeth">${DEFS}
  <ellipse cx="0" cy="1.6" rx="41" ry="3.4" fill="#000" opacity="0.09"/>
  <g>${bob}
  ${foot(false, lw)}
  ${foot(true, lw)}
  <g>${sway}
    <rect x="43.6" y="-104" width="2.2" height="20" rx="0.9" fill="#fff" stroke="${OUT}" stroke-width="${lw * 0.7}"/>
    <rect x="44.6" y="-104" width="1.2" height="20" fill="${SHADE}"/>
    <path d="M20 -130 H70 V-107.5 L66.5 -103.5 H20 Z" fill="#fff" stroke="${OUT}" stroke-width="${lw * 0.9}" stroke-linejoin="round"/>
    <path d="M20.6 -105.6 H66.2 L64.6 -104 H20.6 Z" fill="${SHADE}"/>
    <path d="M70 -107.5 L66.5 -103.5 L66.9 -107.2 Z" fill="#dfe2e7" stroke="${OUT}" stroke-width="${lw * 0.6}" stroke-linejoin="round"/>
    ${signFace}
    <path d="M28.4 -81 C31.6 -85.6,35.4 -90.4,39.2 -93.6 C41.8 -95.8,46.8 -95.2,47.8 -91.6 C48.6 -88.6,47.2 -85.8,44.8 -84 C42.6 -78.4,38.4 -70.4,31 -61 Z" fill="#fff" stroke="${OUT}" stroke-width="${lw}" stroke-linejoin="round"/>
    <path d="M47.6 -90 C47.4 -87.6,46.2 -85.6,44.8 -84 C42.6 -78.4,38.4 -70.4,31 -61 L30.4 -66.6 C35.4 -72.4,40.2 -79.6,43 -85.6 C44.6 -86.4,46.4 -87.8,47.6 -90 Z" fill="${SHADE}"/>
  </g>
  <path d="M-28.4 -79 C-35 -72.4,-41.8 -58,-45 -43 C-45.4 -40.6,-43.4 -39.6,-41.8 -41 C-38 -44.6,-34 -49.4,-30.9 -54 Z" fill="#fff" stroke="${OUT}" stroke-width="${lw}" stroke-linejoin="round"/>
  <path d="M-44.6 -41.4 C-43.6 -40,-42.6 -40.2,-41.8 -41 C-38 -44.6,-34 -49.4,-30.9 -54 L-30.4 -60.4 C-33.6 -55,-38.6 -48,-44.6 -41.4 Z" fill="${SHADE}"/>
  <path d="${BODY}" fill="#fff"/>
  <path d="M19.6 -105 C25.8 -99,28 -92,28.4 -86 C29.4 -72,30.8 -52,31.2 -36 C31.5 -24,30.5 -14,27 -11 C24.6 -10.2,22.2 -9.8,20 -9.8 C23.4 -16,25 -28,25.2 -40 C25.4 -58,24.8 -76,24.2 -86 C23.8 -94,22.4 -100,19.6 -105 Z" fill="${SHADE}"/>
  <path d="M-30.9 -54 C-30.6 -50,-30 -47.6,-28.6 -45.6 C-28.8 -50,-28.8 -55,-28.6 -60 Z" fill="${SHADE}"/>
  <path d="M-30 -18 C-27 -13.4,-20 -11.8,-12 -12.6 C-18 -14.4,-24 -15.6,-30 -18 Z" fill="${SHADE}"/>
  <path d="M-9 -24 C-5.4 -18,-2.2 -15.6,0 -15.4 C2.2 -15.6,5.4 -18,9 -24 C5 -20.2,2.4 -18.8,0 -18.8 C-2.4 -18.8,-5 -20.2,-9 -24 Z" fill="${SHADE_DEEP}" opacity="0.7"/>
  <path d="${BODY}" fill="none" stroke="${OUT}" stroke-width="${lw * 1.1}" stroke-linejoin="round"/>
  ${eye(-12.8, -94.2, lw)}
  ${eye(12.8, -94.2, lw)}
  ${tears}
  ${beak(lw)}
  </g>
</g>`
}
