import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { attendanceMarkingApi } from '../api/attendanceMarkingApi'
import { attendanceSessionsApi } from '../api/attendanceSessionsApi'
import { departmentsApi } from '../api/departmentsApi'
import { getApiError } from '../api/client'
import { useAttendanceSession } from '../context/useAttendanceSession'
import { useAuth } from '../context/useAuth'
import Icon from './Icon'
import StatsCard from './StatsCard'

const SCAN_INTERVAL_MS = 2800
const LIVENESS_FRAME_COUNT = 5
const LIVENESS_FRAME_DELAY_MS = 500
const LIVENESS_CHALLENGES = [
  { type: 'MOVE_LEFT', label: 'Move face slightly left' },
  { type: 'MOVE_RIGHT', label: 'Move face slightly right' },
  { type: 'MOVE_CLOSER', label: 'Move closer to camera' },
]

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function formatConfidence(value) {
  if (typeof value !== 'number') return '-'
  return value.toFixed(6)
}

function mapRecord(record) {
  return {
    id: record.attendanceRecordId,
    studentName: record.studentName,
    rollNo: record.rollNo,
    className: record.className,
    status: record.status,
    recognitionConfidence: record.recognitionConfidence,
    livenessStatus: record.livenessStatus,
    markedAt: record.markedAt,
  }
}

function buildResultMessage(result) {
  if (result.attendanceMarked) {
    return {
      tone: 'success',
      text: `Attendance marked successfully for ${result.studentName || 'matched student'}.`,
    }
  }
  if (result.status === 'DuplicateAttendance') {
    return {
      tone: 'info',
      text: `Attendance already marked for ${result.studentName || 'this student'} in this session.`,
    }
  }
  if (result.status === 'MatchBelowThreshold') {
    return {
      tone: 'warning',
      text: 'Face detected but match confidence is below threshold.',
    }
  }
  if (result.status === 'NoFaceDetected') {
    return {
      tone: 'warning',
      text: 'No face detected. Please face the camera clearly.',
    }
  }
  if (result.status === 'LivenessFailed') {
    return {
      tone: 'warning',
      text: 'Liveness failed. Please try again with your real face in front of the camera. Possible photo/screen spoof detected.',
    }
  }
  if (result.status === 'LivenessPassed') {
    return {
      tone: 'success',
      text: 'Liveness passed, matching face...',
    }
  }
  if (result.status === 'NoActiveSession') {
    return {
      tone: 'error',
      text: 'No active attendance session.',
    }
  }
  return {
    tone: 'info',
    text: result.message || 'Attendance scan completed.',
  }
}

export default function LiveAttendanceStation({ mode = 'admin', pagePath }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const scanningRef = useRef(false)
  const scanInFlightRef = useRef(false)
  const scanTimeoutRef = useRef(null)
  const { assignedDepartmentId, assignedDepartmentName, hasAllDepartmentsAccess } = useAuth()
  const { clearSession, registerCleanup, startSession: startNavigationSession, stopSession: stopNavigationSession } = useAttendanceSession()

  const canChooseDepartment = mode === 'admin' || hasAllDepartmentsAccess()
  const lockedDepartmentId = canChooseDepartment ? '' : assignedDepartmentId || ''

  const [departments, setDepartments] = useState([])
  const [departmentId, setDepartmentId] = useState(lockedDepartmentId)
  const [activeSession, setActiveSession] = useState(null)
  const [records, setRecords] = useState([])
  const [cameraOn, setCameraOn] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [loading, setLoading] = useState(false)
  const [recordsLoading, setRecordsLoading] = useState(false)
  const [message, setMessage] = useState({ tone: 'info', text: 'Select or start an attendance session.' })
  const [lastResult, setLastResult] = useState(null)
  const [currentChallenge, setCurrentChallenge] = useState(null)

  const selectedDepartment = useMemo(() => {
    const selectedId = Number(departmentId)
    return departments.find(department => department.departmentId === selectedId)
  }, [departmentId, departments])

  const departmentLabel = selectedDepartment?.departmentName || assignedDepartmentName || 'Department'

  const stopScanning = useCallback(() => {
    scanningRef.current = false
    setScanning(false)
    if (scanTimeoutRef.current) {
      clearTimeout(scanTimeoutRef.current)
      scanTimeoutRef.current = null
    }
  }, [])

  const stopCamera = useCallback(() => {
    stopScanning()
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOn(false)
  }, [stopScanning])

  const cleanupAttendance = useCallback(() => {
    stopCamera()
    clearSession()
  }, [clearSession, stopCamera])

  const loadRecords = useCallback(async sessionId => {
    if (!sessionId) {
      setRecords([])
      return
    }
    setRecordsLoading(true)
    try {
      const sessionRecords = await attendanceSessionsApi.records(sessionId)
      setRecords(sessionRecords.map(mapRecord))
    } catch (error) {
      setMessage({ tone: 'error', text: getApiError(error, 'Unable to load attendance records.') })
    } finally {
      setRecordsLoading(false)
    }
  }, [])

  const loadActiveSession = useCallback(async targetDepartmentId => {
    if (!targetDepartmentId) {
      setActiveSession(null)
      setRecords([])
      return
    }
    try {
      const sessions = await attendanceSessionsApi.active({ departmentId: targetDepartmentId })
      const session = sessions[0] || null
      setActiveSession(session)
      if (session) {
        setMessage({ tone: 'success', text: `Active session #${session.sessionId} loaded.` })
        startNavigationSession(pagePath)
        await loadRecords(session.sessionId)
      } else {
        setMessage({ tone: 'info', text: 'No active attendance session for this department.' })
        setRecords([])
        stopNavigationSession()
      }
    } catch (error) {
      setActiveSession(null)
      setRecords([])
      setMessage({ tone: 'error', text: getApiError(error, 'Unable to load active attendance session.') })
    }
  }, [loadRecords, pagePath, startNavigationSession, stopNavigationSession])

  useEffect(() => {
    let mounted = true
    departmentsApi.list()
      .then(items => {
        if (!mounted) return
        setDepartments(items)
        if (!canChooseDepartment && assignedDepartmentId) {
          setDepartmentId(assignedDepartmentId)
        } else if (!departmentId && items.length > 0) {
          setDepartmentId(items[0].departmentId)
        }
      })
      .catch(error => {
        if (mounted) setMessage({ tone: 'error', text: getApiError(error, 'Unable to load departments.') })
      })
    return () => {
      mounted = false
    }
  }, [assignedDepartmentId, canChooseDepartment, departmentId])

  useEffect(() => {
    if (departmentId) loadActiveSession(departmentId)
  }, [departmentId, loadActiveSession])

  useEffect(() => {
    registerCleanup(cleanupAttendance)
    return () => registerCleanup(null)
  }, [cleanupAttendance, registerCleanup])

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    if (scanTimeoutRef.current) clearTimeout(scanTimeoutRef.current)
  }, [])

  const startBackendSession = async () => {
    if (!departmentId) {
      setMessage({ tone: 'warning', text: 'Select a department before starting a session.' })
      return
    }
    setLoading(true)
    try {
      const session = await attendanceSessionsApi.start({ departmentId: Number(departmentId) })
      setActiveSession(session)
      startNavigationSession(pagePath)
      setMessage({ tone: 'success', text: `Attendance session #${session.sessionId} started.` })
      await loadRecords(session.sessionId)
    } catch (error) {
      setMessage({ tone: 'error', text: getApiError(error, 'Unable to start attendance session.') })
      await loadActiveSession(departmentId)
    } finally {
      setLoading(false)
    }
  }

  const stopBackendSession = async () => {
    if (!activeSession) return
    setLoading(true)
    stopCamera()
    try {
      await attendanceSessionsApi.stop(activeSession.sessionId)
      setMessage({ tone: 'success', text: `Attendance session #${activeSession.sessionId} stopped.` })
      setActiveSession(null)
      stopNavigationSession()
    } catch (error) {
      setMessage({ tone: 'error', text: getApiError(error, 'Unable to stop attendance session.') })
    } finally {
      setLoading(false)
    }
  }

  const startCamera = async () => {
    if (!activeSession) {
      setMessage({ tone: 'warning', text: 'Start or load an active session before opening the camera.' })
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
      setCameraOn(true)
      setMessage({ tone: 'success', text: 'Camera started. Start scanning when ready.' })
      startNavigationSession(pagePath)
    } catch {
      stopCamera()
      setMessage({ tone: 'error', text: 'Camera permission was denied. Please allow camera access and try again.' })
    }
  }

  const captureFrameBlob = () => new Promise(resolve => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
      resolve(null)
      return
    }
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob(blob => resolve(blob), 'image/jpeg', 0.85)
  })

  const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))

  const captureLivenessFrames = async () => {
    const frames = []
    for (let index = 0; index < LIVENESS_FRAME_COUNT; index += 1) {
      if (!scanningRef.current) break
      const blob = await captureFrameBlob()
      if (blob) frames.push(blob)
      if (index < LIVENESS_FRAME_COUNT - 1) await wait(LIVENESS_FRAME_DELAY_MS)
    }
    return frames
  }

  const chooseChallenge = () => LIVENESS_CHALLENGES[Math.floor(Math.random() * LIVENESS_CHALLENGES.length)]

  const runScan = useCallback(async () => {
    if (!scanningRef.current || !activeSession || !cameraOn || scanInFlightRef.current) return

    scanInFlightRef.current = true
    try {
      const challenge = chooseChallenge()
      setCurrentChallenge(challenge)
      setMessage({ tone: 'info', text: `Liveness challenge: ${challenge.label}` })

      const frames = await captureLivenessFrames()
      if (frames.length < LIVENESS_FRAME_COUNT) {
        setMessage({ tone: 'warning', text: 'Camera frames are not ready yet. Please keep your face in view and retry.' })
        return
      }
      setMessage({ tone: 'info', text: 'Checking liveness...' })
      const result = await attendanceMarkingApi.markByFaceLive({
        sessionId: activeSession.sessionId,
        challengeType: challenge.type,
        files: frames,
      })
      setLastResult(result)
      setMessage(buildResultMessage(result))
      if (result.attendanceMarked || result.status === 'DuplicateAttendance') {
        await loadRecords(activeSession.sessionId)
      }
    } catch (error) {
      const detail = getApiError(error, 'Unable to mark attendance.')
      const isNoActiveSession = detail === 'NoActiveSession'
      setMessage({ tone: 'error', text: isNoActiveSession ? 'No active attendance session.' : detail })
      if (isNoActiveSession) {
        stopScanning()
        setActiveSession(null)
      }
    } finally {
      scanInFlightRef.current = false
      if (scanningRef.current) {
        scanTimeoutRef.current = setTimeout(runScan, SCAN_INTERVAL_MS)
      }
    }
  }, [activeSession, cameraOn, loadRecords, stopScanning])

  const startScanning = () => {
    if (!activeSession) {
      setMessage({ tone: 'warning', text: 'No active attendance session.' })
      return
    }
    if (!cameraOn) {
      setMessage({ tone: 'warning', text: 'Start the camera before scanning.' })
      return
    }
    scanningRef.current = true
    setScanning(true)
    setMessage({ tone: 'info', text: 'Scanning started. Complete one quick liveness challenge per scan.' })
    runScan()
  }

  const handleDepartmentChange = event => {
    stopCamera()
    setActiveSession(null)
    setRecords([])
    setDepartmentId(event.target.value)
  }

  const messageStyle = {
    success: { backgroundColor: '#d1fae5', color: '#065f46' },
    info: { backgroundColor: '#FFF0E6', color: '#795900' },
    warning: { backgroundColor: '#fef3c7', color: '#92400e' },
    error: { backgroundColor: '#ffdad6', color: '#93000a' },
  }[message.tone] || { backgroundColor: '#FFF0E6', color: '#795900' }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Live Attendance</p>
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Attendance Marking</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={startBackendSession} disabled={loading || !departmentId || Boolean(activeSession)} className="px-4 py-2 rounded-lg font-bold text-sm text-white disabled:opacity-60" style={{ backgroundColor: '#D4A017' }}>
            Start Session
          </button>
          <button onClick={stopBackendSession} disabled={loading || !activeSession} className="px-4 py-2 rounded-lg font-bold text-sm text-white disabled:opacity-60" style={{ backgroundColor: '#C4533A' }}>
            Stop Session
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-xl p-5 fdas-card">
          <p className="text-xs font-bold uppercase" style={{ color: '#887369' }}>{canChooseDepartment ? 'Department' : 'Assigned Department'}</p>
          {canChooseDepartment ? (
            <select value={departmentId} onChange={handleDepartmentChange} className="mt-2 w-full rounded-lg border px-3 py-2 text-sm font-bold" style={{ borderColor: '#f0dfd8', color: '#4A2B0F', backgroundColor: '#fff' }}>
              {departments.map(department => (
                <option key={department.departmentId} value={department.departmentId}>{department.departmentName}</option>
              ))}
            </select>
          ) : (
            <p className="text-xl font-black mt-1" style={{ color: '#4A2B0F' }}>{departmentLabel}</p>
          )}
        </div>
        <StatsCard title="Session" value={activeSession ? `#${activeSession.sessionId}` : 'None'} icon="school" />
        <StatsCard title="Present" value={records.length} icon="how_to_reg" iconColor="#D4A017" />
        <StatsCard title="Status" value={activeSession ? 'Active' : 'Closed'} icon="videocam" iconColor={activeSession ? '#065f46' : '#C4533A'} />
      </div>

      <div className="rounded-xl px-4 py-3 text-sm font-bold" style={messageStyle}>
        {message.text}
        {lastResult?.recognitionConfidence !== undefined && (
          <span className="ml-2 font-mono">
            Confidence {formatConfidence(lastResult.recognitionConfidence)}
            {lastResult.thresholdUsed !== undefined ? ` / Threshold ${formatConfidence(lastResult.thresholdUsed)}` : ''}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_420px] gap-5 min-w-0">
        <div className="rounded-xl overflow-hidden border-2 fdas-card" style={{ borderColor: '#FFF0E6' }}>
          <div className="px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b" style={{ borderColor: '#f0dfd8' }}>
            <div>
              <h2 className="font-black" style={{ color: '#4A2B0F' }}>Live Camera Preview</h2>
              <p className="text-xs" style={{ color: '#887369' }}>Scanning uses one basic movement liveness challenge before matching.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={cameraOn ? stopCamera : startCamera} disabled={!activeSession} className="px-3 py-2 rounded-lg text-xs font-bold border disabled:opacity-60" style={{ borderColor: '#C4533A', color: '#C4533A' }}>
                {cameraOn ? 'Stop Camera' : 'Start Camera'}
              </button>
              <button onClick={scanning ? stopScanning : startScanning} disabled={!activeSession || !cameraOn} className="px-3 py-2 rounded-lg text-xs font-bold text-white disabled:opacity-60" style={{ backgroundColor: scanning ? '#C4533A' : '#D4A017' }}>
                {scanning ? 'Stop Scanning' : 'Start Scanning'}
              </button>
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
            <canvas ref={canvasRef} className="hidden" />
            <div className="absolute inset-6 rounded-xl border-2 border-dashed" style={{ borderColor: cameraOn ? '#D4A017' : '#55433b' }} />
            {!cameraOn && (
              <div className="text-center relative z-10 p-8">
                <Icon name="videocam_off" size={80} className="block mx-auto mb-3" style={{ color: '#887369' }} />
                <p className="text-lg font-black" style={{ color: '#fff8f6' }}>Camera stopped</p>
                <p className="mt-2 text-sm font-bold px-4 py-2 rounded-full inline-flex" style={{ backgroundColor: '#C4533A', color: '#fff' }}>Start camera after session is active</p>
              </div>
            )}
            {cameraOn && (
              <>
                <div className="absolute top-5 left-5 rounded-full px-4 py-2 text-xs font-bold" style={{ backgroundColor: 'rgba(196,83,58,0.88)', color: '#fff' }}>
                  Camera Active
                </div>
                <div className="absolute bottom-5 left-5 right-5 rounded-xl p-3 text-center font-bold text-sm" style={{ backgroundColor: scanning ? 'rgba(6,95,70,0.9)' : 'rgba(196,83,58,0.9)', color: '#fff' }}>
                  {scanning ? `Liveness challenge: ${currentChallenge?.label || 'Get ready'}` : 'Camera ready. Start scanning to mark attendance.'}
                </div>
              </>
            )}
          </div>
        </div>

        <div className="rounded-xl border-t-[3px] flex flex-col overflow-hidden" style={{ backgroundColor: '#FFF0E6', borderColor: '#D4A017', boxShadow: '0 4px 20px rgba(232,146,74,0.15)', minHeight: 400, maxHeight: 640 }}>
          <div className="px-5 py-4 flex items-center justify-between border-b" style={{ borderColor: 'rgba(232,146,74,0.2)', backgroundColor: 'rgba(255,255,255,0.5)' }}>
            <h3 className="font-bold text-base" style={{ color: '#C4533A' }}>Session Records</h3>
            <button onClick={() => loadRecords(activeSession?.sessionId)} disabled={!activeSession || recordsLoading} className="text-xs font-bold px-3 py-1 rounded-full disabled:opacity-60" style={{ backgroundColor: 'rgba(212,160,23,0.15)', color: '#795900' }}>
              Refresh
            </button>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead style={{ color: '#887369' }}>
                <tr className="text-left">
                  <th className="px-4 py-3">Student</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Confidence</th>
                  <th className="px-4 py-3">Liveness</th>
                </tr>
              </thead>
              <tbody>
                {records.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="px-4 py-10 text-center" style={{ color: '#887369' }}>No attendance records yet.</td>
                  </tr>
                ) : records.map(record => (
                  <tr key={record.id} className="border-t" style={{ borderColor: 'rgba(232,146,74,0.18)' }}>
                    <td className="px-4 py-3">
                      <div className="font-bold" style={{ color: '#4A2B0F' }}>{record.studentName}</div>
                      <div className="text-[11px] font-mono" style={{ color: '#887369' }}>{record.rollNo}</div>
                      <div className="text-[11px]" style={{ color: '#887369' }}>{record.className}</div>
                      <div className="text-[11px]" style={{ color: '#887369' }}>{formatDateTime(record.markedAt)}</div>
                    </td>
                    <td className="px-4 py-3 font-bold" style={{ color: record.status === 'Present' ? '#065f46' : '#92400e' }}>{record.status}</td>
                    <td className="px-4 py-3 font-mono" style={{ color: '#4A2B0F' }}>{formatConfidence(record.recognitionConfidence)}</td>
                    <td className="px-4 py-3" style={{ color: '#887369' }}>{record.livenessStatus || 'NotChecked'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  )
}

export { SCAN_INTERVAL_MS }
