import { useEffect } from 'react'
import Icon from '../Icon'

const toneMap = {
  success: { icon: 'check_circle', background: '#ecfdf5', border: '#86efac', color: '#065f46' },
  error: { icon: 'error', background: '#fff1f0', border: '#f2b8b5', color: '#93000a' },
  info: { icon: 'info', background: '#fff8e8', border: '#f0d480', color: '#715300' },
}

export default function Toast({ message, tone = 'success', onDismiss, duration = 4000 }) {
  useEffect(() => {
    if (!message || !onDismiss || duration <= 0) return undefined
    const timer = window.setTimeout(onDismiss, duration)
    return () => window.clearTimeout(timer)
  }, [duration, message, onDismiss])

  if (!message) return null
  const style = toneMap[tone] || toneMap.info
  return (
    <div className="fdas-toast" role={tone === 'error' ? 'alert' : 'status'} style={{ backgroundColor: style.background, borderColor: style.border, color: style.color }}>
      <Icon name={style.icon} size={20} />
      <span className="min-w-0 flex-1 text-sm font-bold">{message}</span>
      {onDismiss && <button type="button" onClick={onDismiss} className="fdas-icon-button" aria-label="Dismiss notification"><Icon name="close" size={17} /></button>}
    </div>
  )
}
