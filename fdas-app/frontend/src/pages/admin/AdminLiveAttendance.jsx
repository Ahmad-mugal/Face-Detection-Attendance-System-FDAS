import { useCallback, useState } from 'react'
import AttendanceLogSidebar from '../../components/AttendanceLogSidebar'
import CameraFrameUpload from '../../components/CameraFrameUpload'
import StatsCard from '../../components/StatsCard'
import { useAttendanceSession } from '../../context/useAttendanceSession'
import { LIVE_LOG, SESSIONS } from '../../data/dummyData'

export default function AdminLiveAttendance() {
  const [records, setRecords] = useState(LIVE_LOG)
  const [sessionActive, setSessionActive] = useState(false)
  const [cameraActive, setCameraActive] = useState(false)
  const [startRequest, setStartRequest] = useState(0)
  const activeSession = SESSIONS.find(session => session.status === 'active')
  const { clearSession, registerCleanup, startSession, stopSession } = useAttendanceSession()

  const addRecord = record => {
    setRecords(current => [{ id: Date.now(), ...record }, ...current].slice(0, 12))
  }

  const startAttendance = () => {
    startSession('/admin/attendance/live')
    setSessionActive(true)
    setStartRequest(current => current + 1)
  }

  const stopAttendance = () => {
    stopSession()
  }

  const toggleAttendance = () => {
    if (sessionActive || cameraActive) {
      stopAttendance()
    } else {
      startAttendance()
    }
  }

  const handleCameraStateChange = useCallback(active => {
    setCameraActive(active)
    if (!active) setSessionActive(false)
  }, [])

  const handleCameraError = useCallback(() => {
    setCameraActive(false)
    setSessionActive(false)
    clearSession()
  }, [clearSession])

  const registerCameraCleanup = useCallback(cleanup => {
    registerCleanup(cleanup)
  }, [registerCleanup])

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Live Attendance</p>
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Attendance Marking</h1>
        </div>
        <button onClick={toggleAttendance} className="px-4 py-2 rounded-lg font-bold text-sm text-white" style={{ backgroundColor: sessionActive || cameraActive ? '#C4533A' : '#D4A017' }}>
          {sessionActive || cameraActive ? 'Stop Attendance' : 'Start Attendance'}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Session" value={activeSession?.className || 'None'} icon="school" />
        <StatsCard title="Present" value={records.length} icon="how_to_reg" iconColor="#D4A017" />
        <StatsCard title="Session Status" value={sessionActive ? 'Active' : 'Closed'} subtitle="Dummy state" icon="videocam" iconColor="#E8924A" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-5 min-w-0">
        <CameraFrameUpload
          sessionId={activeSession?.id}
          isActive={sessionActive}
          startRequest={startRequest}
          onCameraStateChange={handleCameraStateChange}
          onCameraError={handleCameraError}
          onRegisterCleanup={registerCameraCleanup}
          onMarkRecord={addRecord}
        />
        <AttendanceLogSidebar records={records} title="Session Log" />
      </div>
    </section>
  )
}
