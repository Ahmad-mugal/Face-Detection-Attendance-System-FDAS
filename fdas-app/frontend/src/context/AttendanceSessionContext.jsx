import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ConfirmDialog } from '../components/ui/Modal'
import { ATTENDANCE_PATHS, AttendanceSessionContext, LEAVE_ATTENDANCE_MESSAGE } from './attendanceSessionCore'

export function AttendanceSessionProvider({ children }) {
  const navigate = useNavigate()
  const cleanupRef = useRef(null)
  const [session, setSession] = useState({ active: false, path: null })
  const [pendingNavigation, setPendingNavigation] = useState(null)

  const registerCleanup = useCallback(cleanup => {
    cleanupRef.current = typeof cleanup === 'function' ? cleanup : null
  }, [])

  const startSession = useCallback(path => {
    setSession({ active: true, path })
  }, [])

  const stopSession = useCallback(() => {
    cleanupRef.current?.()
    cleanupRef.current = null
    setSession({ active: false, path: null })
  }, [])

  const clearSession = useCallback(() => {
    cleanupRef.current = null
    setSession({ active: false, path: null })
  }, [])

  const confirmNavigation = useCallback((nextPath, currentPath, onConfirmed) => {
    if (!session.active) return true
    if (!ATTENDANCE_PATHS.includes(currentPath)) return true
    if (nextPath === currentPath) return true

    setPendingNavigation({ nextPath, onConfirmed })
    return false
  }, [session.active])

  const leaveAttendance = useCallback(() => {
    const pending = pendingNavigation
    setPendingNavigation(null)
    stopSession()
    if (pending?.onConfirmed) pending.onConfirmed()
    else if (pending?.nextPath) navigate(pending.nextPath)
  }, [navigate, pendingNavigation, stopSession])

  useEffect(() => {
    const handleBeforeUnload = event => {
      if (!session.active) return
      event.preventDefault()
      event.returnValue = LEAVE_ATTENDANCE_MESSAGE
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [session.active])

  const value = useMemo(() => ({
    isAttendanceActive: session.active,
    attendancePath: session.path,
    confirmNavigation,
    clearSession,
    registerCleanup,
    startSession,
    stopSession,
  }), [clearSession, confirmNavigation, registerCleanup, session.active, session.path, startSession, stopSession])

  return (
    <AttendanceSessionContext.Provider value={value}>
      {children}
      <ConfirmDialog
        open={Boolean(pendingNavigation)}
        onClose={() => setPendingNavigation(null)}
        onConfirm={leaveAttendance}
        title="Leave live attendance?"
        description={LEAVE_ATTENDANCE_MESSAGE}
        confirmLabel="Leave Page"
        destructive
      />
    </AttendanceSessionContext.Provider>
  )
}
