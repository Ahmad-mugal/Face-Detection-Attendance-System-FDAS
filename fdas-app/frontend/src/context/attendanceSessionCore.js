import { createContext } from 'react'

export const ATTENDANCE_PATHS = ['/admin/attendance/live', '/user/attendance']
export const LEAVE_ATTENDANCE_MESSAGE = 'Attendance session is active. Leaving this page will stop the camera/session. Do you want to continue?'
export const AttendanceSessionContext = createContext(null)
