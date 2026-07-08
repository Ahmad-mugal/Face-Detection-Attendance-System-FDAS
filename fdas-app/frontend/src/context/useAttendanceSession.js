import { useContext } from 'react'
import { AttendanceSessionContext } from './attendanceSessionCore'

export function useAttendanceSession() {
  const context = useContext(AttendanceSessionContext)
  if (!context) throw new Error('useAttendanceSession must be used within AttendanceSessionProvider')
  return context
}
