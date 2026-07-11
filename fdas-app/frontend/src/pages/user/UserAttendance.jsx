import { useCallback, useEffect, useRef, useState } from 'react'
import AttendanceLogSidebar from '../../components/AttendanceLogSidebar'
import { useAttendanceSession } from '../../context/useAttendanceSession'
import { LIVE_LOG, SESSIONS } from '../../data/dummyData'
import Icon from '../../components/Icon'

const ASSIGNED_DEPARTMENT = 'Computer Science'

export default function UserAttendance() {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [records, setRecords] = useState(LIVE_LOG.slice(0, 4))
  const [sessionStatus, setSessionStatus] = useState('ready')
  const [message, setMessage] = useState('Liveness ready. Please blink when the camera starts.')
  const [cameraOn, setCameraOn] = useState(false)
  const activeSession = SESSIONS[0]
  const { clearSession, registerCleanup, startSession, stopSession } = useAttendanceSession()

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOn(false)
  }, [])

  const startAttendance = async () => {
    startSession('/user/attendance')
    setMessage('Requesting camera access...')

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      streamRef.current = mediaStream
      if (videoRef.current) videoRef.current.srcObject = mediaStream
      setCameraOn(true)
      setSessionStatus('active')
      setMessage('Please blink')
      setRecords(current => [{ id: Date.now(), studentName: 'Demo Student', rollNumber: 'CS-DEMO-001', markedAt: new Date().toLocaleTimeString(), confidence: 0.94 }, ...current].slice(0, 10))
    } catch {
      stopCamera()
      clearSession()
      setSessionStatus('ready')
      setMessage('Camera permission was denied. Please allow camera access and try again.')
    }
  }

  const stopAttendance = () => {
    stopSession()
    setSessionStatus('closed')
    setMessage('Session closed. Duplicate entries are blocked in this dummy UI.')
  }

  const toggleAttendance = () => {
    if (sessionStatus === 'active' || cameraOn) {
      stopAttendance()
    } else {
      startAttendance()
    }
  }

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
  }, [])

  useEffect(() => {
    registerCleanup(stopCamera)
    return () => registerCleanup(null)
  }, [registerCleanup, stopCamera])

  const showDuplicate = () => setMessage('Duplicate attempt detected: student already marked today.')
  const showLiveness = () => setMessage('Liveness challenge failed: please blink clearly and face the camera.')

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Attendance Session</p>
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>{activeSession.className}</h1>
        </div>
        <button onClick={toggleAttendance} className="px-4 py-2 rounded-lg font-bold text-sm text-white" style={{ backgroundColor: sessionStatus === 'active' || cameraOn ? '#C4533A' : '#D4A017' }}>
          {sessionStatus === 'active' || cameraOn ? 'Stop Attendance' : 'Start Attendance'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl p-5 fdas-card">
          <p className="text-xs font-bold uppercase" style={{ color: '#887369' }}>Assigned Department</p>
          <p className="text-xl font-black mt-1" style={{ color: '#4A2B0F' }}>{ASSIGNED_DEPARTMENT}</p>
        </div>
        <div className="rounded-xl p-5 fdas-card">
          <p className="text-xs font-bold uppercase" style={{ color: '#887369' }}>Attendance Window</p>
          <p className="text-xl font-black mt-1" style={{ color: '#C4533A' }}>08:00 - 09:30</p>
        </div>
        <div className="rounded-xl p-5 fdas-card">
          <p className="text-xs font-bold uppercase" style={{ color: '#887369' }}>Session Status</p>
          <p className="text-xl font-black mt-1 capitalize" style={{ color: sessionStatus === 'active' ? '#065f46' : sessionStatus === 'closed' ? '#93000a' : '#934619' }}>{sessionStatus}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-5 min-w-0">
        <div className="rounded-xl overflow-hidden border-2 fdas-card" style={{ borderColor: '#FFF0E6' }}>
          <div className="px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b" style={{ borderColor: '#f0dfd8' }}>
            <div>
              <h2 className="font-black" style={{ color: '#4A2B0F' }}>Live Camera Preview</h2>
              <p className="text-xs" style={{ color: '#887369' }}>Static dummy attendance station. No real face recognition.</p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-3 py-1 rounded-full text-xs font-bold" style={{ backgroundColor: sessionStatus === 'active' ? '#d1fae5' : '#ffdad6', color: sessionStatus === 'active' ? '#065f46' : '#93000a' }}>
                {sessionStatus === 'active' ? 'Session Active' : 'Session Inactive'}
              </span>
              {cameraOn && (
                <span className="px-3 py-1 rounded-full text-xs font-bold" style={{ backgroundColor: '#FFF0E6', color: '#D4A017' }}>Camera Active</span>
              )}
            </div>
          </div>
          <div className="relative min-h-[380px] flex items-center justify-center" style={{ backgroundColor: '#221a16' }}>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 h-full w-full object-cover"
              style={{ display: cameraOn ? 'block' : 'none' }}
            />
            <div className="absolute inset-6 rounded-xl border-2 border-dashed" style={{ borderColor: cameraOn ? '#D4A017' : '#55433b' }} />
            {!cameraOn && (
              <div className="text-center relative z-10 p-8">
                <Icon name="videocam_off" size={80} className="block mx-auto mb-3" style={{ color: '#887369' }} />
                <p className="text-lg font-black" style={{ color: '#fff8f6' }}>Camera stopped</p>
                <p className="mt-2 text-sm font-bold px-4 py-2 rounded-full inline-flex" style={{ backgroundColor: '#C4533A', color: '#fff' }}>{message}</p>
              </div>
            )}
            {cameraOn && (
              <div className="absolute top-5 left-5 rounded-full px-4 py-2 text-xs font-bold" style={{ backgroundColor: 'rgba(196,83,58,0.88)', color: '#fff' }}>
                Camera Active
              </div>
            )}
            {cameraOn && (
              <div className="absolute bottom-5 left-5 right-5 rounded-xl p-3 text-center font-bold text-sm" style={{ backgroundColor: 'rgba(196,83,58,0.9)', color: '#fff' }}>
                Liveness Challenge: Please blink
              </div>
            )}
            {cameraOn && (
              <div className="absolute top-5 right-5 max-w-[calc(100%-2.5rem)] text-right">
              <p className="mt-2 text-sm font-bold px-4 py-2 rounded-full inline-flex" style={{ backgroundColor: '#C4533A', color: '#fff' }}>{message}</p>
            </div>
            )}
          </div>
          <div className="p-4 flex flex-wrap gap-2" style={{ backgroundColor: '#FFF0E6' }}>
            <button onClick={showDuplicate} className="px-3 py-2 rounded-lg text-xs font-bold border" style={{ borderColor: '#C4533A', color: '#C4533A' }}>Show Duplicate Message</button>
            <button onClick={showLiveness} className="px-3 py-2 rounded-lg text-xs font-bold border" style={{ borderColor: '#D4A017', color: '#715300' }}>Show Liveness Message</button>
          </div>
        </div>
        <AttendanceLogSidebar records={records} title="Today Marked Students" />
      </div>
    </section>
  )
}
