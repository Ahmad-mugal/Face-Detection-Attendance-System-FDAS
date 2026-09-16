export const PREFERENCES_KEY = 'fdas.account.preferences'

export const defaultPreferences = {
  tableDensity: 'comfortable',
  autoRefreshAttendance: true,
  reducedMotion: false,
}

export function loadPreferences() {
  try {
    return { ...defaultPreferences, ...JSON.parse(localStorage.getItem(PREFERENCES_KEY) || '{}') }
  } catch {
    return { ...defaultPreferences }
  }
}

export function applyPreferences(preferences) {
  document.documentElement.dataset.tableDensity = preferences.tableDensity
  document.documentElement.dataset.reducedMotion = preferences.reducedMotion ? 'true' : 'false'
}

export function savePreferences(preferences) {
  localStorage.setItem(PREFERENCES_KEY, JSON.stringify(preferences))
  applyPreferences(preferences)
}

export function applyStoredPreferences() {
  applyPreferences(loadPreferences())
}
