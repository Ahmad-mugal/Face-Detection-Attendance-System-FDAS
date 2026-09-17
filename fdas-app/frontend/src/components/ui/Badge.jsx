import Icon from '../Icon'

const toneByLabel = {
  active: 'success',
  approved: 'success',
  enrolled: 'success',
  passed: 'success',
  present: 'success',
  ready: 'success',
  pending: 'warning',
  incomplete: 'warning',
  inactive: 'neutral',
  archived: 'neutral',
  disabled: 'danger',
  failed: 'danger',
  'not enrolled': 'danger',
}

export default function Badge({ children, tone, icon, className = '' }) {
  const label = String(children || '').toLowerCase()
  const resolvedTone = tone || toneByLabel[label] || 'neutral'
  return (
    <span className={`fdas-badge fdas-badge-${resolvedTone} ${className}`.trim()}>
      {icon && <Icon name={icon} size={13} aria-hidden="true" />}
      {children}
    </span>
  )
}
