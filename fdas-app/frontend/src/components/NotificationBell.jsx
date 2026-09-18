import { useCallback, useEffect, useState } from 'react'
import { notificationsApi } from '../api/notificationsApi'
import Icon from './Icon'

export const NOTIFICATION_POLL_INTERVAL_MS = 12000

function relativeTime(value) {
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return 'Recently'
  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000))
  if (seconds < 60) return 'Just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return days < 7 ? `${days}d ago` : new Date(value).toLocaleDateString()
}

function severityTone(severity) {
  if (severity === 'SUCCESS') return '#087a68'
  if (severity === 'WARNING') return '#a45b00'
  if (severity === 'ACTION_REQUIRED') return '#ba1a1a'
  return '#795900'
}

export default function NotificationBell({ open, onToggle, onNavigate, color = '#C4533A' }) {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadNotifications = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true)
    try {
      const result = await notificationsApi.list()
      setNotifications(result.notifications)
      setUnreadCount(result.unreadCount)
      setError('')
    } catch {
      if (!silent) setError('Notifications are temporarily unavailable.')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadNotifications()
    const timer = window.setInterval(() => loadNotifications({ silent: true }), NOTIFICATION_POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [loadNotifications])

  useEffect(() => {
    if (open) loadNotifications()
  }, [open, loadNotifications])

  const markReadAndNavigate = async notification => {
    if (!notification.isRead) {
      try {
        const updated = await notificationsApi.markRead(notification.notificationId)
        setNotifications(current => current.map(item => item.notificationId === updated.notificationId ? updated : item))
        setUnreadCount(current => Math.max(0, current - 1))
      } catch {
        setError('Unable to mark the notification as read.')
        return
      }
    }
    if (notification.actionUrl) onNavigate(notification.actionUrl)
  }

  const markAllRead = async () => {
    try {
      await notificationsApi.markAllRead()
      setNotifications(current => current.map(item => ({ ...item, isRead: true })))
      setUnreadCount(0)
    } catch {
      setError('Unable to mark notifications as read.')
    }
  }

  return (
    <div className="relative" onPointerDown={event => event.stopPropagation()}>
      <button
        type="button"
        onClick={onToggle}
        className="fdas-icon-button relative"
        style={{ color }}
        aria-label={unreadCount ? `Open notifications, ${unreadCount} unread` : 'Open notifications'}
        aria-haspopup="dialog"
        aria-expanded={open}
        title="Notifications"
      >
        <Icon name="notifications" size={20} />
        {unreadCount > 0 && <span className="fdas-notification-count" aria-hidden="true">{unreadCount > 99 ? '99+' : unreadCount}</span>}
      </button>

      {open && (
        <section className="fdas-notification-popover" role="dialog" aria-label="Notifications">
          <header className="fdas-notification-header">
            <div>
              <p className="fdas-eyebrow mb-0">Notification Center</p>
              <p className="text-sm font-bold mt-1" style={{ color: '#4A2B0F' }}>{unreadCount ? `${unreadCount} unread update${unreadCount === 1 ? '' : 's'}` : 'You are all caught up'}</p>
            </div>
            <button type="button" onClick={markAllRead} disabled={!unreadCount} className="fdas-button fdas-button-ghost fdas-button-sm">Mark all read</button>
          </header>

          <div className="fdas-notification-list">
            {loading ? (
              <div className="fdas-notification-empty">Loading notifications…</div>
            ) : error ? (
              <div className="fdas-notification-empty" role="alert">{error}</div>
            ) : notifications.length === 0 ? (
              <div className="fdas-notification-empty">No notifications yet. Important FDAS updates will appear here.</div>
            ) : notifications.map(notification => (
              <article key={notification.notificationId} className={`fdas-notification-item ${notification.isRead ? '' : 'fdas-notification-item-unread'}`}>
                <span className="fdas-notification-severity" style={{ backgroundColor: severityTone(notification.severity) }} aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-sm font-black" style={{ color: '#4A2B0F' }}>{notification.title}</h3>
                    <time className="text-[11px] whitespace-nowrap" style={{ color: '#887369' }} dateTime={notification.createdAt}>{relativeTime(notification.createdAt)}</time>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed" style={{ color: '#6f5b52' }}>{notification.message}</p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <span className="text-[10px] font-black tracking-wide" style={{ color: severityTone(notification.severity) }}>{notification.severity.replace('_', ' ')}</span>
                    {(notification.actionUrl || !notification.isRead) && (
                      <button type="button" onClick={() => markReadAndNavigate(notification)} className="text-xs font-bold underline underline-offset-2" style={{ color: '#934619' }}>
                        {notification.actionUrl ? 'Open' : 'Mark read'}
                      </button>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
          <footer className="fdas-notification-footer">Updates refresh automatically every 12 seconds.</footer>
        </section>
      )}
    </div>
  )
}
