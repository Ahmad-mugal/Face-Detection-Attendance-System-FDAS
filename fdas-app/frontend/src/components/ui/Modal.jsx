import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../Icon'

const widthClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-3xl',
  wide: 'max-w-5xl',
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
  busy = false,
  closeOnBackdrop = true,
  showClose = true,
}) {
  const titleId = useId()
  const descriptionId = useId()
  const panelRef = useRef(null)
  const returnFocusRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    returnFocusRef.current = document.activeElement
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const focusable = () => Array.from(panelRef.current?.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ) || [])

    const focusTimer = window.setTimeout(() => {
      const elements = focusable()
      ;(elements[0] || panelRef.current)?.focus()
    }, 0)

    const handleKeyDown = event => {
      if (event.key === 'Escape' && !busy) {
        event.preventDefault()
        onClose?.()
        return
      }
      if (event.key !== 'Tab') return
      const elements = focusable()
      if (!elements.length) {
        event.preventDefault()
        panelRef.current?.focus()
        return
      }
      const first = elements[0]
      const last = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      window.clearTimeout(focusTimer)
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
      window.setTimeout(() => returnFocusRef.current?.focus?.(), 0)
    }
  }, [busy, onClose, open])

  if (!open) return null

  return createPortal(
    <div
      className="fdas-modal-backdrop"
      onMouseDown={event => {
        if (event.target === event.currentTarget && closeOnBackdrop && !busy) onClose?.()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className={`fdas-modal-panel ${widthClasses[size] || widthClasses.md}`}
      >
        <header className="fdas-modal-header">
          <div className="min-w-0">
            <h2 id={titleId} className="text-xl font-black" style={{ color: '#4A2B0F' }}>{title}</h2>
            {description && <p id={descriptionId} className="mt-1 text-sm" style={{ color: '#6f5b52' }}>{description}</p>}
          </div>
          {showClose && (
            <button type="button" onClick={onClose} disabled={busy} className="fdas-icon-button" aria-label={`Close ${title}`}>
              <Icon name="close" size={20} />
            </button>
          )}
        </header>
        <div className="fdas-modal-body">{children}</div>
        {footer && <footer className="fdas-modal-footer">{footer}</footer>}
      </div>
    </div>,
    document.body,
  )
}

export function FormDialog({ open, onClose, onSubmit, title, description, children, submitLabel = 'Save Changes', busy = false, size = 'md' }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      busy={busy}
      size={size}
      footer={(
        <>
          <button type="button" onClick={onClose} disabled={busy} className="fdas-button fdas-button-secondary">Cancel</button>
          <button type="submit" form="fdas-dialog-form" disabled={busy} className="fdas-button fdas-button-primary">
            {busy ? 'Saving…' : submitLabel}
          </button>
        </>
      )}
    >
      <form id="fdas-dialog-form" onSubmit={onSubmit}>{children}</form>
    </Modal>
  )
}

export function ConfirmDialog({ open, onClose, onConfirm, title, description, confirmLabel = 'Confirm', busy = false, destructive = false, children }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      busy={busy}
      size="sm"
      footer={(
        <>
          <button type="button" onClick={onClose} disabled={busy} className="fdas-button fdas-button-secondary">Cancel</button>
          <button type="button" onClick={onConfirm} disabled={busy} className={`fdas-button ${destructive ? 'fdas-button-danger' : 'fdas-button-primary'}`}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </>
      )}
    >
      {children}
    </Modal>
  )
}
