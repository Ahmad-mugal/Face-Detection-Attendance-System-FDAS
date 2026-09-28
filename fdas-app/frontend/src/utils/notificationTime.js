export function parseBackendUtc(value) {
  if (!value) return null

  const text = String(value).trim()
  if (!text) return null

  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text)
  const parsed = new Date(hasTimezone ? text : `${text}Z`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function notificationRelativeTime(value, now = new Date()) {
  const timestamp = parseBackendUtc(value)
  const current = now instanceof Date ? now : parseBackendUtc(now)
  if (!timestamp || !current || Number.isNaN(current.getTime())) return 'Recently'

  const seconds = Math.max(0, Math.floor((current.getTime() - timestamp.getTime()) / 1000))
  if (seconds < 60) return 'Just now'

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`

  const days = Math.floor(hours / 24)
  return days < 7 ? `${days}d ago` : timestamp.toLocaleDateString()
}
