export function fmt(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (!Number.isFinite(value)) return '∞'
  return Number(value).toLocaleString('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export const pct = (value, digits = 0) => `%${fmt(value * 100, digits)}`

export function hoursToText(h) {
  if (!Number.isFinite(h)) return '—'
  const hh = Math.floor(h)
  const mm = Math.round((h - hh) * 60)
  return mm === 60 ? `${hh + 1} sa 0 dk` : `${hh} sa ${mm} dk`
}
