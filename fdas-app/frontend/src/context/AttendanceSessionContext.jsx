import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ATTENDANCE_PATHS, AttendanceSessionContext, LEAVE_ATTENDANCE_MESSAGE } from './attendanceSessionCore'

export function AttendanceSessionProvider({ children }) {
  const cleanupRef = useRef(null)
  const [session, setSession] = useState({ active: false, path: null })

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

  const confirmNavigation = useCallback((nextPath, currentPath) => {
    if (!session.active) return true
    if (!ATTENDANCE_PATHS.includes(currentPath)) return true
    if (nextPath === currentPath) return true

    const shouldLeave = window.confirm(LEAVE_ATTENDANCE_MESSAGE)
    if (shouldLeave) stopSession()
    return shouldLeave
  }, [session.active, stopSession])

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
    </AttendanceSessionContext.Provider>
  )
}
