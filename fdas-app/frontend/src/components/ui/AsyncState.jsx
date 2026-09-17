import Icon from '../Icon'

export function LoadingState({ label = 'Loading…', compact = false }) {
  return (
    <div className={`fdas-state ${compact ? 'fdas-state-compact' : ''}`} role="status" aria-live="polite">
      <span className="fdas-spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  )
}

export function EmptyState({ title = 'No data available', description, icon = 'inbox' }) {
  return (
    <div className="fdas-state">
      <span className="fdas-state-icon"><Icon name={icon} size={25} aria-hidden="true" /></span>
      <p className="fdas-state-title">{title}</p>
      {description && <p className="fdas-state-description">{description}</p>}
    </div>
  )
}
