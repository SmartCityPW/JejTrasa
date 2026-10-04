export const LEVEL_COLORS = {
  safe: '#7C3AED',
  moderate: '#E59A0B',
  risky: '#E11D48',
}

export function scoreColor(score) {
  if (score >= 82) return '#5B21B6'
  if (score >= 75) return '#8B5CF6'
  if (score >= 65) return '#C4A2F7'
  if (score >= 55) return '#F5A524'
  if (score >= 45) return '#F97316'
  return '#E11D48'
}

export function levelOf(score) {
  if (score >= 75) return { id: 'safe', label: 'Bezpieczna' }
  if (score >= 55) return { id: 'moderate', label: 'Umiarkowana' }
  return { id: 'risky', label: 'Ryzykowna' }
}

export function fmtDistance(m) {
  if (m == null) return ''
  return m >= 1000 ? `${(m / 1000).toFixed(1).replace('.', ',')} km` : `${Math.round(m)} m`
}

export function fmtMinutes(min) {
  if (min < 60) return `${min} min`
  return `${Math.floor(min / 60)} h ${min % 60} min`
}

export function pct(v) {
  return `${Math.round(v * 100)}%`
}

/** Lokalny czas ISO bez strefy: 2026-10-04T22:30 */
export function toLocalIso(date) {
  const p = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}T${p(date.getHours())}:${p(date.getMinutes())}`
}

export function nowRounded() {
  const d = new Date()
  d.setMinutes(Math.round(d.getMinutes() / 5) * 5, 0, 0)
  return toLocalIso(d)
}

export function withTime(iso, hhmm) {
  return `${iso.slice(0, 10)}T${hhmm}`
}

export function timeOf(iso) {
  return iso.slice(11, 16)
}

export function minutesOf(iso) {
  const [h, m] = timeOf(iso).split(':').map(Number)
  return h * 60 + m
}

export function fmtDateLong(iso) {
  const d = new Date(iso)
  return d.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' })
}

export function plural(n, one, few, many) {
  if (n === 1) return one
  const d = n % 10
  const t = n % 100
  if (d >= 2 && d <= 4 && (t < 12 || t > 14)) return few
  return many
}

const R = 6371000
export function haversine(a, b) {
  const toRad = (x) => (x * Math.PI) / 180
  const dLat = toRad(b[0] - a[0])
  const dLon = toRad(b[1] - a[1])
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

/** Przygotowuje polilinię do interpolacji pozycji (symulacja chodzenia). */
export function buildTrack(coords) {
  const cum = [0]
  for (let i = 1; i < coords.length; i++) cum.push(cum[i - 1] + haversine(coords[i - 1], coords[i]))
  return { coords, cum, total: cum[cum.length - 1] }
}

export function pointAt(track, dist) {
  const { coords, cum } = track
  if (dist <= 0) return { pos: coords[0], index: 0 }
  if (dist >= track.total) return { pos: coords[coords.length - 1], index: coords.length - 1 }
  let lo = 0
  let hi = cum.length - 1
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1
    if (cum[mid] <= dist) lo = mid
    else hi = mid
  }
  const t = (dist - cum[lo]) / (cum[hi] - cum[lo] || 1)
  const a = coords[lo]
  const b = coords[hi]
  return { pos: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], index: lo }
}
