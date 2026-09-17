import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { attendanceMarkingApi } from '../api/attendanceMarkingApi'
import { attendanceSessionsApi } from '../api/attendanceSessionsApi'
import { departmentsApi } from '../api/departmentsApi'
import { faceMatchingApi } from '../api/faceMatchingApi'
import { getApiError } from '../api/client'
import { studentsApi } from '../api/studentsApi'
import { useAttendanceSession } from '../context/useAttendanceSession'
import { useAuth } from '../context/useAuth'
import Icon from './Icon'
import { loadPreferences } from '../utils/preferences'
import StatsCard from './StatsCard'
import PageHeader from './ui/PageHeader'

const SCAN_INTERVAL_MS = 1800
const LIVENESS_BASELINE_FRAME_COUNT = 2
const LIVENESS_MOVEMENT_FRAME_COUNT = 10
const LIVENESS_FRAME_COUNT = LIVENESS_BASELINE_FRAME_COUNT + LIVENESS_MOVEMENT_FRAME_COUNT
const LIVENESS_BASELINE_DELAY_MS = 250
const LIVENESS_FRAME_DELAY_MS = 300
const LIVENESS_CENTER_HOLD_MS = 1500
const LIVENESS_GO_RENDER_MS = 600
const ATTENDANCE_SINGLE_FACE_STABLE_MS = 1000
const RECOGNITION_RECENTER_HOLD_MS = 1200
const RECOGNITION_QUERY_COUNT = 3
const RECOGNITION_QUERY_DELAY_MS = 350
const CONTROLLED_MAX_RETRIES = 2
const CONTROLLED_RELIABILITY_CYCLES = 10
const LIVENESS_CHALLENGES = [
  { type: 'MOVE_CLOSER', label: 'Move closer to camera and hold' },
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

function formatLivenessMeasurement(value) {
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
      text: 'Attendance already marked for this session.',
    }
  }
  if (result.status === 'MatchBelowThreshold') {
    return {
      tone: 'warning',
      text: 'Face could not be verified. Please try again.',
    }
  }
  if (result.status === 'AmbiguousMatch') {
    return {
      tone: 'warning',
      text: 'Identity could not be confirmed safely. Please try again.',
    }
  }
  if (result.status === 'QueryConsensusFailed') {
    return { tone: 'warning', text: 'Identity could not be confirmed safely. Please try again.' }
  }
  if (result.status === 'PoorFaceQuality') {
    const qualityReasons = (result.queryQuality || [])
      .filter(query => query?.passed === false)
      .flatMap(query => String(query.reason || '').split(','))
    if (qualityReasons.includes('blurred')) {
      return { tone: 'warning', text: 'Image is blurry. Hold still and look at the camera.' }
    }
    if (qualityReasons.some(reason => ['too_dark', 'too_bright'].includes(reason))) {
      return { tone: 'warning', text: 'Lighting is too dark or too bright. Adjust your position.' }
    }
    if (qualityReasons.some(reason => ['face_too_small', 'face_near_edge'].includes(reason))) {
      return { tone: 'warning', text: 'Keep your face centered in the camera.' }
    }
    return { tone: 'warning', text: 'Face image quality was insufficient. Hold still and look at the camera.' }
  }
  if (result.status === 'InvalidQueryBurst') {
    return { tone: 'error', text: 'The required three-image recognition burst was incomplete. Attendance was not marked.' }
  }
  if (result.status === 'AttendanceSafetyHold') {
    return {
      tone: 'warning',
      text: 'Attendance remains disabled while identity-integrity validation is incomplete.',
    }
  }
  if (result.status === 'DeepRecognitionUnavailable') {
    return { tone: 'error', text: 'Deep recognition is unavailable. Attendance was not marked and no legacy fallback was used.' }
  }
  if (result.status === 'DeepEnrollmentIncomplete' || result.status === 'DeepIncomplete') {
    return { tone: 'warning', text: 'Face registration is incomplete. Please contact the administrator.' }
  }
  if (result.status === 'ControlledIdentityMismatch') {
    return { tone: 'warning', text: 'The face did not match the authorized controlled-test student. Attendance was not marked.' }
  }
  if (result.status === 'NoFaceDetected') {
    return {
      tone: 'warning',
      text: 'No face detected. Please face the camera.',
    }
  }
  if (result.status === 'MultipleFacesDetected') {
    return {
      tone: 'warning',
      text: 'Only one person should be in front of the camera.',
    }
  }
  if (result.status === 'FaceContinuityLost') {
    return {
      tone: 'warning',
      text: 'Face tracking was lost. Please try again.',
    }
  }
  if (result.status === 'LivenessFailed') {
    return {
      tone: 'warning',
      text: 'Movement was not detected clearly. Move closer after GO and hold.',
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
  const showDevelopmentDiagnostics = mode === 'diagnostic'
  const autoRefreshAttendance = loadPreferences().autoRefreshAttendance
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const scanningRef = useRef(false)
  const scanInFlightRef = useRef(false)
  const scanTimeoutRef = useRef(null)
  const lastChallengeIndexRef = useRef(-1)
  const controlledCycleRef = useRef(1)
  const controlledRetryRef = useRef(0)
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
  const [controlledTestResults, setControlledTestResults] = useState([])
  const [currentChallenge, setCurrentChallenge] = useState(null)
  const [livenessInstruction, setLivenessInstruction] = useState(null)
  const [diagnosticStudents, setDiagnosticStudents] = useState([])
  const [expectedStudentId, setExpectedStudentId] = useState('')
  const [diagnosticLoading, setDiagnosticLoading] = useState(false)
  const [identityDiagnostic, setIdentityDiagnostic] = useState(null)
  const [diagnosticHistory, setDiagnosticHistory] = useState([])
  const [attendanceFaceGuard, setAttendanceFaceGuard] = useState({
    status: 'Unchecked',
    message: 'No face detected.',
    ready: false,
  })
  const [deepAttendancePolicy, setDeepAttendancePolicy] = useState({
    integratedForAttendance: false,
    activeForAttendance: false,
    attendanceSafetyHold: true,
    controlledAttendanceEnabled: false,
    controlledAttendanceStudentId: null,
    controlledAttendanceStudentName: null,
    controlledAttendanceStudentRollNo: null,
    controlledAttendanceDepartmentId: null,
    controlledAttendanceValidEmbeddingCount: 0,
    controlledAttendanceStudentReady: false,
    controlledAttendanceReady: false,
    controlledMatchingThreshold: null,
    controlledRequiredIdentityMargin: null,
    deepRecognitionReady: false,
  })

  const controlledAttendanceMode = (
    mode === 'admin'
    && deepAttendancePolicy.integratedForAttendance
    && deepAttendancePolicy.attendanceSafetyHold
    && !deepAttendancePolicy.activeForAttendance
    && deepAttendancePolicy.controlledAttendanceEnabled
    && deepAttendancePolicy.controlledAttendanceStudentId === 22
    && deepAttendancePolicy.controlledAttendanceStudentReady
    && deepAttendancePolicy.controlledAttendanceReady
    && deepAttendancePolicy.deepRecognitionReady
  )
  const controlledAttendanceSessionAllowed = (
    controlledAttendanceMode
    && Boolean(activeSession)
    && Number(activeSession.departmentId) === deepAttendancePolicy.controlledAttendanceDepartmentId
    && Number(departmentId) === deepAttendancePolicy.controlledAttendanceDepartmentId
  )
  const normalAttendanceAllowed = (
    deepAttendancePolicy.activeForAttendance
    && !deepAttendancePolicy.attendanceSafetyHold
  )
  const attendanceScanningEnabled = normalAttendanceAllowed || controlledAttendanceSessionAllowed

  const selectedDepartment = useMemo(() => {
    const selectedId = Number(departmentId)
    return departments.find(department => department.departmentId === selectedId)
  }, [departmentId, departments])

  const departmentLabel = selectedDepartment?.departmentName || assignedDepartmentName || 'Department'

  const stopScanning = useCallback(() => {
    scanningRef.current = false
    setScanning(false)
    setLivenessInstruction(null)
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
    faceMatchingApi.getDeepInfo()
      .then(info => {
        if (mounted) setDeepAttendancePolicy(info)
      })
      .catch(error => {
        if (mounted) setMessage({ tone: 'error', text: getApiError(error, 'Unable to load deep attendance safety state.') })
      })
    return () => { mounted = false }
  }, [])

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
    let mounted = true
    if (!showDevelopmentDiagnostics) {
      setDiagnosticStudents([])
      setExpectedStudentId('')
      return () => { mounted = false }
    }
    if (!departmentId) {
      setDiagnosticStudents([])
      setExpectedStudentId('')
      return () => { mounted = false }
    }
    studentsApi.list({ departmentId: Number(departmentId), status: 'Active' })
      .then(items => {
        if (!mounted) return
        const encodedStudents = items.filter(student => student.hasEncodedFaceTemplates)
        setDiagnosticStudents(encodedStudents)
        setExpectedStudentId(current => (
          encodedStudents.some(student => String(student.studentId) === String(current))
            ? current
            : ''
        ))
      })
      .catch(error => {
        if (mounted) setMessage({ tone: 'error', text: getApiError(error, 'Unable to load diagnostic students.') })
      })
    return () => { mounted = false }
  }, [departmentId, showDevelopmentDiagnostics])

  useEffect(() => {
    if (!autoRefreshAttendance || !activeSession?.sessionId) return undefined
    const interval = window.setInterval(() => loadRecords(activeSession.sessionId), 15000)
    return () => window.clearInterval(interval)
  }, [activeSession?.sessionId, autoRefreshAttendance, loadRecords])

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

  const inspectAttendanceFrame = async (frame, referenceFile = null) => {
    const result = await faceMatchingApi.validateSingleFace({ file: frame, referenceFile, attendanceMode: true })
    const message = result.status === 'NoFaceDetected'
      ? 'No face detected. Please stand in front of the camera.'
      : result.status === 'MultipleFacesDetected'
        ? 'Multiple faces detected. Please allow only one student in front of the camera for attendance.'
        : result.status === 'FaceContinuityLost'
          ? 'The active face changed or disappeared. This attendance attempt was cancelled.'
          : 'Face detected — ready.'
    const guardResult = { ...result, message }
    setAttendanceFaceGuard(guardResult)
    return guardResult
  }

  const captureLivenessFrames = async (frameCount, frameDelayMs, referenceFile) => {
    const frames = []
    for (let index = 0; index < frameCount; index += 1) {
      if (!scanningRef.current) break
      const blob = await captureFrameBlob()
      if (blob) {
        const faceGuardResult = await inspectAttendanceFrame(blob, referenceFile)
        if (!faceGuardResult.ready || faceGuardResult.faceCount !== 1 || faceGuardResult.continuityPassed === false) {
          return { frames, faceGuardFailure: faceGuardResult }
        }
        frames.push(blob)
      }
      if (index < frameCount - 1) await wait(frameDelayMs)
    }
    return { frames, faceGuardFailure: null }
  }

  const chooseChallenge = () => {
    const nextIndex = (lastChallengeIndexRef.current + 1) % LIVENESS_CHALLENGES.length
    lastChallengeIndexRef.current = nextIndex
    return LIVENESS_CHALLENGES[nextIndex]
  }

  const runScan = useCallback(async () => {
    if (!scanningRef.current || !activeSession || !cameraOn || scanInFlightRef.current) return

    scanInFlightRef.current = true
    try {
      const initialFace = await captureFrameBlob()
      if (!initialFace) {
        setMessage({ tone: 'warning', text: 'Camera frame is not ready yet.' })
        return
      }
      const initialGuard = await inspectAttendanceFrame(initialFace)
      if (!initialGuard.ready || initialGuard.faceCount !== 1) {
        setMessage({ tone: 'warning', text: initialGuard.message })
        return
      }
      await wait(ATTENDANCE_SINGLE_FACE_STABLE_MS)
      if (!scanningRef.current) return
      const stableFace = await captureFrameBlob()
      if (!stableFace) {
        setMessage({ tone: 'warning', text: 'Camera frame is not ready yet.' })
        return
      }
      const stableGuard = await inspectAttendanceFrame(stableFace, initialFace)
      if (!stableGuard.ready || stableGuard.faceCount !== 1 || stableGuard.continuityPassed === false) {
        setMessage({ tone: 'warning', text: stableGuard.message })
        return
      }

      const challenge = chooseChallenge()
      setCurrentChallenge(challenge)
      setLivenessInstruction('Stay centered')
      setMessage({ tone: 'info', text: 'Stay centered.' })
      await wait(LIVENESS_CENTER_HOLD_MS)
      if (!scanningRef.current) return

      const baselineCapture = await captureLivenessFrames(
        LIVENESS_BASELINE_FRAME_COUNT,
        LIVENESS_BASELINE_DELAY_MS,
        stableFace,
      )
      if (baselineCapture.faceGuardFailure) {
        setMessage({ tone: 'warning', text: baselineCapture.faceGuardFailure.message })
        return
      }
      const baselineFrames = baselineCapture.frames
      if (baselineFrames.length < LIVENESS_BASELINE_FRAME_COUNT) {
        setMessage({ tone: 'warning', text: 'Stable baseline frames were not ready. Please center your face and retry.' })
        return
      }

      setLivenessInstruction('GO — move closer to the camera and HOLD')
      setMessage({ tone: 'info', text: 'GO — move closer to the camera, then hold that position until capture finishes.' })
      await wait(LIVENESS_GO_RENDER_MS)
      if (!scanningRef.current) return

      const movementCapture = await captureLivenessFrames(
        LIVENESS_MOVEMENT_FRAME_COUNT,
        LIVENESS_FRAME_DELAY_MS,
        stableFace,
      )
      if (movementCapture.faceGuardFailure) {
        setMessage({ tone: 'warning', text: movementCapture.faceGuardFailure.message })
        return
      }
      const movementFrames = movementCapture.frames
      const frames = [...baselineFrames, ...movementFrames]
      if (frames.length < LIVENESS_FRAME_COUNT) {
        setMessage({ tone: 'warning', text: 'Camera frames are not ready yet. Please keep your face in view and retry.' })
        return
      }
      setLivenessInstruction('Return to center and hold still for recognition')
      setMessage({ tone: 'info', text: 'Movement captured. Return to center, face forward, and hold still.' })
      await wait(RECOGNITION_RECENTER_HOLD_MS)
      if (!scanningRef.current) return
      const queryCapture = await captureLivenessFrames(
        RECOGNITION_QUERY_COUNT,
        RECOGNITION_QUERY_DELAY_MS,
        stableFace,
      )
      if (queryCapture.faceGuardFailure) {
        setMessage({ tone: 'warning', text: queryCapture.faceGuardFailure.message })
        return
      }
      if (queryCapture.frames.length !== RECOGNITION_QUERY_COUNT) {
        setMessage({ tone: 'warning', text: 'Fresh recognition images were not ready. Please remain centered and retry.' })
        return
      }

      const cycle = controlledAttendanceSessionAllowed ? controlledCycleRef.current : null
      const retryNumber = controlledAttendanceSessionAllowed ? controlledRetryRef.current : 0
      setMessage({ tone: 'info', text: 'Checking liveness and three-image identity consensus...' })
      const result = await attendanceMarkingApi.markByFaceLive({
        sessionId: activeSession.sessionId,
        challengeType: challenge.type,
        files: frames,
        queryFiles: queryCapture.frames,
        controlledTest: controlledAttendanceSessionAllowed,
        expectedStudentId: controlledAttendanceSessionAllowed ? deepAttendancePolicy.controlledAttendanceStudentId : undefined,
      })
      setLastResult(result)
      if (controlledAttendanceSessionAllowed) {
        setControlledTestResults(previous => [
          ...previous,
          {
            attempt: previous.length + 1,
            cycle,
            retryNumber,
            observedAt: new Date().toISOString(),
            status: result.status,
            attendanceMarked: result.attendanceMarked,
            attendanceRecordId: result.attendanceRecordId,
            sessionId: result.sessionId,
            studentId: result.studentId,
            studentName: result.studentName,
            rollNo: result.rollNo,
            recognitionConfidence: result.recognitionConfidence,
            recognitionProvider: result.recognitionProvider,
            recognitionEncodingVersion: result.recognitionEncodingVersion,
            recognitionMethod: result.recognitionMethod,
            aggregationMethod: result.aggregationMethod,
            identityMargin: result.identityMargin,
            topStudentId: result.topStudentId,
            topScore: result.topScore,
            secondStudentId: result.secondStudentId,
            secondScore: result.secondScore,
            scoreMargin: result.scoreMargin,
            thresholdUsed: result.thresholdUsed,
            requiredMargin: result.requiredMargin,
            livenessStatus: result.livenessStatus,
            controlledTest: result.controlledTest,
            queryCount: result.queryCount,
            validQueryCount: result.validQueryCount,
            consensusStudentId: result.consensusStudentId,
            consensusCount: result.consensusCount,
            queryTopStudentIds: result.queryTopStudentIds,
            queryTopScores: result.queryTopScores,
            queryQuality: result.queryQuality,
            retryable: result.retryable,
            livenessDiagnostics: result.livenessDiagnostics,
          },
        ])
      }
      setMessage(buildResultMessage(result))
      if (result.attendanceMarked || result.status === 'DuplicateAttendance') {
        await loadRecords(activeSession.sessionId)
      }
      if (controlledAttendanceSessionAllowed) {
        const retryable = result.retryable || [
          'LivenessFailed',
          'NoFaceDetected',
          'FaceContinuityLost',
          'PoorFaceQuality',
          'MatchBelowThreshold',
          'AmbiguousMatch',
          'QueryConsensusFailed',
        ].includes(result.status)
        if (retryable && controlledRetryRef.current < CONTROLLED_MAX_RETRIES) {
          controlledRetryRef.current += 1
        } else {
          controlledCycleRef.current += 1
          controlledRetryRef.current = 0
        }
        if (controlledCycleRef.current > CONTROLLED_RELIABILITY_CYCLES) {
          stopScanning()
          setMessage({ tone: 'success', text: `Phase 10.9B controlled policy validation completed: ${CONTROLLED_RELIABILITY_CYCLES} cycles recorded.` })
        }
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
  }, [activeSession, cameraOn, controlledAttendanceSessionAllowed, deepAttendancePolicy.controlledAttendanceStudentId, loadRecords, stopScanning])

  const startScanning = () => {
    if (!activeSession) {
      setMessage({ tone: 'warning', text: 'No active attendance session.' })
      return
    }
    if (!cameraOn) {
      setMessage({ tone: 'warning', text: 'Start the camera before scanning.' })
      return
    }
    if (!attendanceScanningEnabled) {
      setMessage({ tone: 'warning', text: 'Deep attendance remains paused by the identity safety hold.' })
      return
    }
    scanningRef.current = true
    if (controlledAttendanceSessionAllowed) {
      controlledCycleRef.current = 1
      controlledRetryRef.current = 0
      lastChallengeIndexRef.current = -1
      setControlledTestResults([])
    }
    setScanning(true)
    setMessage({ tone: 'info', text: 'Scanning started. Complete one quick liveness challenge per scan.' })
    runScan()
  }

  const copyControlledTestReport = async () => {
    const acceptedStatuses = ['AttendanceMarked', 'DuplicateAttendance']
    const attemptedCycles = [...new Set(controlledTestResults.map(item => item.cycle).filter(Boolean))]
    const firstAttemptAcceptedCycles = [...new Set(controlledTestResults.filter(item => item.retryNumber === 0 && acceptedStatuses.includes(item.status)).map(item => item.cycle))]
    const retryAssistedAcceptedCycles = [...new Set(controlledTestResults.filter(item => item.retryNumber > 0 && acceptedStatuses.includes(item.status)).map(item => item.cycle))]
    const livenessPassedAttempts = controlledTestResults.filter(item => item.livenessStatus === 'Passed')
    const recognitionAttempts = controlledTestResults.filter(item => item.validQueryCount === RECOGNITION_QUERY_COUNT)
    const genuineAccepts = recognitionAttempts.filter(item => acceptedStatuses.includes(item.status) && (item.studentId ?? item.topStudentId) === deepAttendancePolicy.controlledAttendanceStudentId)
    const numericRange = (items, field) => {
      const values = items.map(item => item[field]).filter(value => typeof value === 'number')
      return values.length ? { minimum: Math.min(...values), maximum: Math.max(...values) } : null
    }
    const percentage = (numerator, denominator) => denominator ? Number(((numerator / denominator) * 100).toFixed(1)) : 0
    const report = {
      phase: '10.9B',
      generatedAt: new Date().toISOString(),
      sessionId: activeSession?.sessionId ?? null,
      expectedStudentId: deepAttendancePolicy.controlledAttendanceStudentId,
      identityMatchingSafetyHold: deepAttendancePolicy.attendanceSafetyHold,
      deepRecognitionActiveForAttendance: deepAttendancePolicy.activeForAttendance,
      controlledAttendanceEnabled: deepAttendancePolicy.controlledAttendanceEnabled,
      productionThreshold: deepAttendancePolicy.threshold,
      productionMargin: deepAttendancePolicy.requiredIdentityMargin,
      controlledThreshold: deepAttendancePolicy.controlledMatchingThreshold,
      controlledMargin: deepAttendancePolicy.controlledRequiredIdentityMargin,
      consensusMinimum: 2,
      reliabilityCyclesTarget: CONTROLLED_RELIABILITY_CYCLES,
      maximumRetriesPerCycle: CONTROLLED_MAX_RETRIES,
      cyclesAttempted: attemptedCycles.length,
      totalAttempts: controlledTestResults.length,
      livenessFirstAttemptPasses: controlledTestResults.filter(item => item.retryNumber === 0 && item.livenessStatus === 'Passed').length,
      livenessRetryPasses: controlledTestResults.filter(item => item.retryNumber > 0 && item.livenessStatus === 'Passed').length,
      livenessFailures: controlledTestResults.filter(item => item.livenessStatus === 'Failed').length,
      recognitionAttemptsReachingArcFace: recognitionAttempts.length,
      threeOfThreeConsensus: recognitionAttempts.filter(item => item.consensusCount === 3).length,
      twoOfThreeConsensus: recognitionAttempts.filter(item => item.consensusCount === 2).length,
      genuineAccepts: genuineAccepts.length,
      genuineRejects: recognitionAttempts.length - genuineAccepts.length,
      wrongTopIdentityCount: recognitionAttempts.filter(item => item.topStudentId && item.topStudentId !== deepAttendancePolicy.controlledAttendanceStudentId).length,
      falseDistinctIdentityAcceptCount: controlledTestResults.filter(item => acceptedStatuses.includes(item.status) && (item.studentId ?? item.topStudentId) !== deepAttendancePolicy.controlledAttendanceStudentId).length,
      scoreRange: numericRange(recognitionAttempts, 'topScore'),
      secondPersonScoreRange: numericRange(recognitionAttempts, 'secondScore'),
      marginRange: numericRange(recognitionAttempts, 'scoreMargin'),
      retryAttemptsRequired: controlledTestResults.filter(item => item.retryNumber > 0).length,
      livenessSuccessRatePercent: percentage(livenessPassedAttempts.length, controlledTestResults.length),
      recognitionSuccessGivenLivenessPercent: percentage(genuineAccepts.length, recognitionAttempts.length),
      firstAttemptCycleSuccessPercent: percentage(firstAttemptAcceptedCycles.length, attemptedCycles.length),
      retryAssistedCycleSuccessPercent: percentage(retryAssistedAcceptedCycles.length, attemptedCycles.length),
      overallCycleSuccessPercent: percentage(new Set([...firstAttemptAcceptedCycles, ...retryAssistedAcceptedCycles]).size, attemptedCycles.length),
      firstAttemptAcceptedCycles: firstAttemptAcceptedCycles.length,
      retryAssistedAcceptedCycles: retryAssistedAcceptedCycles.length,
      falseAcceptCount: controlledTestResults.filter(item => item.attendanceMarked && item.studentId !== deepAttendancePolicy.controlledAttendanceStudentId).length,
      results: controlledTestResults,
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2))
      setMessage({ tone: 'success', text: 'Controlled Phase 10.9B policy evidence copied. Paste it into the Codex chat.' })
    } catch {
      setMessage({ tone: 'error', text: 'Unable to copy the controlled evidence. Please copy it from the panel manually.' })
    }
  }

  const handleDepartmentChange = event => {
    stopCamera()
    setActiveSession(null)
    setRecords([])
    setIdentityDiagnostic(null)
    setDiagnosticHistory([])
    setExpectedStudentId('')
    setDepartmentId(event.target.value)
  }

  const runIdentityDiagnostic = async () => {
    stopScanning()
    if (!cameraOn) {
      setMessage({ tone: 'warning', text: 'Start the camera before running an identity diagnostic.' })
      return
    }
    if (!departmentId || !expectedStudentId) {
      setMessage({ tone: 'warning', text: 'Select the enrolled person or Unknown / not enrolled.' })
      return
    }

    setDiagnosticLoading(true)
    try {
      const frame = await captureFrameBlob()
      if (!frame) {
        setMessage({ tone: 'warning', text: 'Camera frame is not ready. Keep your face visible and retry.' })
        return
      }
      const result = await faceMatchingApi.diagnose({
        departmentId: Number(departmentId),
        expectedStudentId: expectedStudentId === 'unknown' ? undefined : Number(expectedStudentId),
        file: frame,
      })
      setIdentityDiagnostic(result)
      setDiagnosticHistory(current => [
        ...current,
        {
          ...result,
          captureNumber: current.length + 1,
          expectedLabel: expectedStudentId === 'unknown' ? 'Unknown / not enrolled' : `Student #${expectedStudentId}`,
          capturedAt: new Date().toISOString(),
          usable: result.status === 'DiagnosticComplete',
        },
      ])
      setMessage({
        tone: result.status === 'DiagnosticComplete' ? 'info' : 'warning',
        text: `${result.message} No attendance was created.`,
      })
    } catch (error) {
      setMessage({ tone: 'error', text: getApiError(error, 'Unable to run identity diagnostic.') })
    } finally {
      setDiagnosticLoading(false)
    }
  }

  const messageStyle = {
    success: { backgroundColor: '#d1fae5', color: '#065f46' },
    info: { backgroundColor: '#FFF0E6', color: '#795900' },
    warning: { backgroundColor: '#fef3c7', color: '#92400e' },
    error: { backgroundColor: '#ffdad6', color: '#93000a' },
  }[message.tone] || { backgroundColor: '#FFF0E6', color: '#795900' }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <PageHeader eyebrow="Live Attendance" title="Attendance Marking" description="Start a session, verify one-person liveness, and record eligible attendance securely." actions={
        <div className="flex flex-wrap gap-2">
          <button onClick={startBackendSession} disabled={loading || !departmentId || Boolean(activeSession)} className="fdas-button fdas-button-warning">
            Start Session
          </button>
          <button onClick={stopBackendSession} disabled={loading || !activeSession} className="fdas-button fdas-button-outline">
            Stop Session
          </button>
        </div>
      } />

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 sm:p-5 fdas-card">
          <p className="text-xs font-bold uppercase" style={{ color: '#887369' }}>{canChooseDepartment ? 'Department' : 'Assigned Department'}</p>
          {canChooseDepartment ? (
            <select value={departmentId} onChange={handleDepartmentChange} className="fdas-input mt-2 font-bold">
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
      </div>

      {showDevelopmentDiagnostics && controlledAttendanceMode && (
        <div className="rounded-xl border px-4 py-3 text-sm" style={{ backgroundColor: '#fff8e8', borderColor: '#d4a017', color: '#5f4300' }}>
          <strong>Phase 10.9B controlled policy enabled:</strong> only canonical Student #{deepAttendancePolicy.controlledAttendanceStudentId} {deepAttendancePolicy.controlledAttendanceStudentName} ({deepAttendancePolicy.controlledAttendanceStudentRollNo}) may be persisted. Controlled threshold {formatConfidence(deepAttendancePolicy.controlledMatchingThreshold)} and margin {formatConfidence(deepAttendancePolicy.controlledRequiredIdentityMargin)} apply only here; production remains {formatConfidence(deepAttendancePolicy.threshold)} / {formatConfidence(deepAttendancePolicy.requiredIdentityMargin)}. Deep readiness: {deepAttendancePolicy.controlledAttendanceValidEmbeddingCount} valid embeddings. The global identity safety hold remains active; all other automatic attendance stays disabled.
        </div>
      )}

      {showDevelopmentDiagnostics && controlledAttendanceMode && controlledTestResults.length > 0 && (
        <div className="rounded-xl border px-4 py-3 text-xs space-y-3" style={{ backgroundColor: '#fff', borderColor: '#d4a017', color: '#55433b' }}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="font-black text-sm" style={{ color: '#4A2B0F' }}>Phase 10.9B Controlled Policy Evidence</p>
              <p>Runs 10 cycles with at most 2 fresh retries per cycle. Images and raw embeddings are never stored.</p>
            </div>
            <button type="button" onClick={copyControlledTestReport} className="fdas-button fdas-button-success fdas-button-sm">
              Copy Controlled Test Report
            </button>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-left whitespace-nowrap">
              <thead><tr><th className="py-1 pr-3">Attempt</th><th className="py-1 pr-3">Cycle / retry</th><th className="py-1 pr-3">Result</th><th className="py-1 pr-3">Top</th><th className="py-1 pr-3">Second</th><th className="py-1 pr-3">Margin</th><th className="py-1 pr-3">Consensus</th><th className="py-1">Liveness</th></tr></thead>
              <tbody>
                {controlledTestResults.map(result => (
                  <tr key={`${result.attempt}-${result.observedAt}`} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                    <td className="py-1 pr-3 font-mono">{result.attempt}</td>
                    <td className="py-1 pr-3 font-mono">{result.cycle ?? '-'} / {result.retryNumber ?? 0}</td>
                    <td className="py-1 pr-3 font-bold">{result.status}</td>
                    <td className="py-1 pr-3 font-mono">#{result.topStudentId ?? result.studentId ?? '-'} {formatConfidence(result.topScore ?? result.recognitionConfidence)}</td>
                    <td className="py-1 pr-3 font-mono">#{result.secondStudentId ?? '-'} {formatConfidence(result.secondScore)}</td>
                    <td className="py-1 pr-3 font-mono">{formatConfidence(result.scoreMargin ?? result.identityMargin)}</td>
                    <td className="py-1 pr-3 font-mono">#{result.consensusStudentId ?? '-'} {result.consensusCount ?? 0}/{result.queryCount ?? 0}</td>
                    <td className="py-1 font-mono">{result.livenessStatus || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showDevelopmentDiagnostics && lastResult?.livenessDiagnostics && (
        <div className="rounded-xl px-4 py-3 text-xs space-y-1 border font-mono" style={{ backgroundColor: '#fff', borderColor: '#f0dfd8', color: '#55433b' }}>
          <p className="font-sans font-black text-sm" style={{ color: '#4A2B0F' }}>Liveness Diagnostic Measurements</p>
          <p>
            Challenge {lastResult.livenessDiagnostics.challenge} | Faces {lastResult.livenessDiagnostics.detectedFaceFrameCount}/{lastResult.livenessDiagnostics.submittedFrameCount} | Baseline {lastResult.livenessDiagnostics.baselineDetectedFaceFrameCount}/{lastResult.livenessDiagnostics.baselineFrameCount} | Movement {lastResult.livenessDiagnostics.movementDetectedFaceFrameCount}/{lastResult.livenessDiagnostics.movementFrameCount}
          </p>
          <p>
            Haar multi-face frames {lastResult.livenessDiagnostics.haarMultipleFaceFrameCount ?? 0} | SCRFD background reconciliations {lastResult.livenessDiagnostics.deepReconciledFrameCount ?? 0}
          </p>
          <p>
            Center X start/end/min/max: {formatLivenessMeasurement(lastResult.livenessDiagnostics.startCenterX)} / {formatLivenessMeasurement(lastResult.livenessDiagnostics.endCenterX)} / {formatLivenessMeasurement(lastResult.livenessDiagnostics.minimumCenterX)} / {formatLivenessMeasurement(lastResult.livenessDiagnostics.maximumCenterX)}
          </p>
          <p>
            Raw signed displacement: {formatLivenessMeasurement(lastResult.livenessDiagnostics.signedDisplacementPixels)} px | Final ratio {formatLivenessMeasurement(lastResult.livenessDiagnostics.displacementRatio)} | Preview-left excursion {formatLivenessMeasurement(lastResult.livenessDiagnostics.leftwardExcursionRatio)} | Preview-right excursion {formatLivenessMeasurement(lastResult.livenessDiagnostics.rightwardExcursionRatio)}
          </p>
          <p>
            Requested-direction ratio: {formatLivenessMeasurement(lastResult.livenessDiagnostics.requestedDirectionalDisplacementRatio)} | Supporting frames {lastResult.livenessDiagnostics.directionalSupportingFrameCount ?? '-'} | Threshold {formatLivenessMeasurement(lastResult.livenessDiagnostics.centerShiftThreshold)}
          </p>
          <p>
            Area start/final/max: {formatLivenessMeasurement(lastResult.livenessDiagnostics.initialFaceArea)} / {formatLivenessMeasurement(lastResult.livenessDiagnostics.finalFaceArea)} / {formatLivenessMeasurement(lastResult.livenessDiagnostics.maximumFaceArea)} | Growth {formatLivenessMeasurement(lastResult.livenessDiagnostics.areaGrowthRatio)} | Max growth {formatLivenessMeasurement(lastResult.livenessDiagnostics.maximumAreaGrowthRatio)}
          </p>
          <p>
            Supporting frames {lastResult.livenessDiagnostics.directionalSupportingFrameCount ?? 0} | Maximum consecutive support {lastResult.livenessDiagnostics.maximumConsecutiveSupportingFrames ?? 0}/{lastResult.livenessDiagnostics.requiredConsecutiveSupportingFrames ?? 2}
          </p>
          <p className="font-sans">Reason: {lastResult.livenessDiagnostics.reason || '-'}</p>
          <p className="font-sans">Method: {lastResult.livenessDiagnostics.evaluationMethod}</p>
        </div>
      )}

      {showDevelopmentDiagnostics && lastResult?.queryQuality?.length > 0 && (
        <div className="rounded-xl px-4 py-3 text-xs space-y-1 border font-mono" style={{ backgroundColor: '#fff', borderColor: '#d4a017', color: '#55433b' }}>
          <p className="font-sans font-black text-sm" style={{ color: '#4A2B0F' }}>Recognition Query Quality & Consensus</p>
          <p>Valid queries {lastResult.validQueryCount}/{lastResult.queryCount} | Consensus #{lastResult.consensusStudentId ?? '-'} {lastResult.consensusCount}/{lastResult.queryCount}</p>
          {lastResult.queryQuality.map(query => (
            <p key={query.queryIndex}>
              Query {query.queryIndex}: {query.status} | area {formatLivenessMeasurement(query.faceAreaRatio)} | blur {formatLivenessMeasurement(query.blurVariance)} | brightness {formatLivenessMeasurement(query.brightness)} | edge {formatLivenessMeasurement(query.edgeClearanceRatio)}{query.haarBackgroundFalsePositiveReconciled ? ' | Haar false-positive reconciled by SCRFD' : ''}
            </p>
          ))}
        </div>
      )}

      {attendanceFaceGuard.status !== 'Unchecked' && (
        <div
          className="rounded-xl px-4 py-3 text-sm font-bold border"
          style={{
            backgroundColor: attendanceFaceGuard.ready ? '#d1fae5' : '#ffdad6',
            borderColor: attendanceFaceGuard.ready ? '#15803d' : '#93000a',
            color: attendanceFaceGuard.ready ? '#065f46' : '#93000a',
          }}
        >
          {attendanceFaceGuard.message}
        </div>
      )}

      {showDevelopmentDiagnostics && <div className="rounded-xl p-4 border space-y-4" style={{ backgroundColor: '#fff', borderColor: '#93000a' }}>
        <div>
          <p className="font-black text-base" style={{ color: '#93000a' }}>Identity Integrity Diagnostic — Attendance Disabled for This Check</p>
          <p className="text-xs mt-1" style={{ color: '#55433b' }}>
            Select the person physically in front of the webcam, or Unknown / not enrolled, then capture one normal frame. This diagnostic compares maximum, top-3 mean, top-5 mean, and top-5 median scores; it never creates attendance or stores the query image.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_auto] gap-3 items-end">
          <label>
            <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Expected person in front of camera</span>
            <select
              value={expectedStudentId}
              onChange={event => setExpectedStudentId(event.target.value)}
              className="fdas-input mt-1 font-bold"
            >
              <option value="">Select student</option>
              <option value="unknown">Unknown / not enrolled</option>
              {diagnosticStudents.map(student => (
                <option key={student.studentId} value={student.studentId}>
                  #{student.studentId} — {student.fullName} ({student.rollNo})
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={runIdentityDiagnostic}
            disabled={!cameraOn || !expectedStudentId || diagnosticLoading}
            className="fdas-button fdas-button-danger"
          >
            {diagnosticLoading ? 'Checking…' : 'Capture Diagnostic — No Attendance'}
          </button>
        </div>
        {identityDiagnostic && (
          <div className="rounded-lg border p-3 text-xs space-y-2" style={{ borderColor: '#f0dfd8', backgroundColor: '#fff8f6', color: '#55433b' }}>
            <p className="font-bold" style={{ color: '#4A2B0F' }}>
              Expected #{identityDiagnostic.expectedStudentId ?? '-'} score {formatConfidence(identityDiagnostic.expectedStudentScore)} | Threshold {formatConfidence(identityDiagnostic.thresholdUsed)} | Attendance created: {identityDiagnostic.attendanceCreated ? 'YES' : 'NO'}
            </p>
            <p className="font-mono">
              Top: {identityDiagnostic.topCandidate ? `#${identityDiagnostic.topCandidate.studentId} ${identityDiagnostic.topCandidate.studentName} (${identityDiagnostic.topCandidate.rollNo}) — ${formatConfidence(identityDiagnostic.topCandidate.bestScore)}` : '-'}
            </p>
            <p className="font-mono">
              Second: {identityDiagnostic.secondCandidate ? `#${identityDiagnostic.secondCandidate.studentId} ${identityDiagnostic.secondCandidate.studentName} (${identityDiagnostic.secondCandidate.rollNo}) — ${formatConfidence(identityDiagnostic.secondCandidate.bestScore)}` : '-'}
            </p>
            <p className="font-mono">Top-1 / top-2 margin: {formatConfidence(identityDiagnostic.scoreMargin)} | Required {formatConfidence(identityDiagnostic.requiredMargin)} | Method {identityDiagnostic.aggregationMethod} | Students {identityDiagnostic.candidateStudentCount} | Templates {identityDiagnostic.candidateTemplateCount}</p>
            <div className="overflow-auto">
              <table className="w-full text-left">
                <thead><tr><th className="py-1 pr-3">Method</th><th className="py-1 pr-3">Expected</th><th className="py-1 pr-3">Top</th><th className="py-1 pr-3">Second</th><th className="py-1">Margin</th></tr></thead>
                <tbody>
                  {(identityDiagnostic.aggregations || []).map(aggregation => (
                    <tr key={aggregation.method} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                      <td className="py-1 pr-3 font-bold">{aggregation.method}</td>
                      <td className="py-1 pr-3 font-mono">{formatConfidence(aggregation.expectedStudentScore)}</td>
                      <td className="py-1 pr-3 font-mono">#{aggregation.topStudentId ?? '-'} {formatConfidence(aggregation.topScore)}</td>
                      <td className="py-1 pr-3 font-mono">#{aggregation.secondStudentId ?? '-'} {formatConfidence(aggregation.secondScore)}</td>
                      <td className="py-1 font-mono">{formatConfidence(aggregation.scoreMargin)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="overflow-auto">
              <table className="w-full text-left">
                <thead><tr><th className="py-1 pr-3">Candidate</th><th className="py-1 pr-3">Maximum</th><th className="py-1 pr-3">Top-3 mean</th><th className="py-1 pr-3">Top-5 mean</th><th className="py-1 pr-3">Top-5 median</th><th className="py-1">Templates</th></tr></thead>
                <tbody>
                  {identityDiagnostic.candidates.map(candidate => (
                    <tr key={candidate.studentId} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                      <td className="py-1 pr-3">#{candidate.studentId} {candidate.studentName} ({candidate.rollNo})</td>
                      <td className="py-1 pr-3 font-mono">{formatConfidence(candidate.maximumScore)}</td>
                      <td className="py-1 pr-3 font-mono">{formatConfidence(candidate.meanTop3Score)}</td>
                      <td className="py-1 pr-3 font-mono">{formatConfidence(candidate.meanTop5Score)}</td>
                      <td className="py-1 pr-3 font-mono">{formatConfidence(candidate.medianTop5Score)}</td>
                      <td className="py-1 font-mono">{candidate.templatesEvaluated}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {diagnosticHistory.length > 0 && (
          <div className="rounded-lg border p-3 text-xs space-y-2" style={{ borderColor: '#dbc1b7', backgroundColor: '#fff', color: '#55433b' }}>
            <p className="font-bold" style={{ color: '#4A2B0F' }}>
              Diagnostic capture log: {diagnosticHistory.filter(item => item.usable).length} usable / {diagnosticHistory.length} attempted. Query images are not stored.
            </p>
            <div className="overflow-auto max-h-64">
              <table className="w-full text-left">
                <thead><tr><th className="py-1 pr-3">#</th><th className="py-1 pr-3">Expected</th><th className="py-1 pr-3">Status</th><th className="py-1 pr-3">Top</th><th className="py-1 pr-3">Second</th><th className="py-1">Margin</th></tr></thead>
                <tbody>
                  {diagnosticHistory.map(item => (
                    <tr key={`${item.captureNumber}-${item.capturedAt}`} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                      <td className="py-1 pr-3 font-mono">{item.captureNumber}</td>
                      <td className="py-1 pr-3">{item.expectedLabel}</td>
                      <td className="py-1 pr-3">{item.status}</td>
                      <td className="py-1 pr-3 font-mono">#{item.topCandidate?.studentId ?? '-'} {formatConfidence(item.topCandidate?.bestScore)}</td>
                      <td className="py-1 pr-3 font-mono">#{item.secondCandidate?.studentId ?? '-'} {formatConfidence(item.secondCandidate?.bestScore)}</td>
                      <td className="py-1 font-mono">{formatConfidence(item.scoreMargin)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_420px] gap-5 min-w-0">
        <div className="overflow-hidden fdas-card" style={{ borderColor: '#e8cec4' }}>
          <div className="px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b" style={{ borderColor: '#f0dfd8' }}>
            <div>
              <h2 className="font-black" style={{ color: '#4A2B0F' }}>Live Camera</h2>
              <p className="text-xs" style={{ color: '#887369' }}>Follow the on-screen instruction, then return to the center and hold still.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={cameraOn ? () => { stopCamera(); setMessage({ tone: 'info', text: 'Camera stopped.' }) } : startCamera} disabled={!activeSession} className="fdas-button fdas-button-outline fdas-button-sm">
                {cameraOn ? 'Stop Camera' : 'Start Camera'}
              </button>
              <button onClick={scanning ? stopScanning : startScanning} disabled={!attendanceScanningEnabled || !activeSession || !cameraOn} className={`fdas-button fdas-button-sm ${scanning ? 'fdas-button-primary' : 'fdas-button-warning'}`}>
                {scanning
                  ? 'Stop Scanning'
                  : (attendanceScanningEnabled ? 'Start Scanning' : 'Attendance Paused')}
              </button>
            </div>
          </div>
          <div className="relative min-h-[340px] sm:min-h-[400px] flex items-center justify-center" style={{ backgroundColor: '#221a16' }}>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 h-full w-full object-cover"
              style={{ display: cameraOn ? 'block' : 'none', transform: 'scaleX(-1)' }}
            />
            <canvas ref={canvasRef} className="hidden" />
            <div className="absolute inset-6 rounded-xl border-2 border-dashed" style={{ borderColor: cameraOn ? '#D4A017' : '#55433b' }} />
            {!cameraOn && (
              <div className="text-center relative z-10 p-8">
                <Icon name="videocam_off" size={80} className="block mx-auto mb-3" style={{ color: '#887369' }} />
                <p className="text-lg font-black" style={{ color: '#fff8f6' }}>Camera stopped</p>
                <p className="mt-2 text-sm font-bold px-4 py-2 rounded-full inline-flex" style={{ backgroundColor: '#C4533A', color: '#fff' }}>{activeSession ? 'Start the camera when you are ready' : 'Start a session to enable the camera'}</p>
              </div>
            )}
            {cameraOn && (
              <>
                <div className="absolute top-5 left-5 rounded-full px-4 py-2 text-xs font-bold" style={{ backgroundColor: 'rgba(196,83,58,0.88)', color: '#fff' }}>
                  Camera Active
                </div>
                <div className="absolute bottom-5 left-5 right-5 rounded-xl p-3 text-center font-bold text-sm" style={{ backgroundColor: scanning ? 'rgba(6,95,70,0.9)' : 'rgba(196,83,58,0.9)', color: '#fff' }}>
                  {scanning
                    ? (livenessInstruction || `Liveness challenge: ${currentChallenge?.label || 'Get ready'}`)
                    : (!attendanceScanningEnabled ? 'Attendance scanning is currently unavailable.' : 'Camera ready. Start scanning to mark attendance.')}
                </div>
              </>
            )}
          </div>
        </div>

        <div className="fdas-card border-t-[3px] flex flex-col overflow-hidden" style={{ backgroundColor: '#FFF0E6', borderTopColor: '#D4A017', minHeight: 380, maxHeight: 640 }}>
          <div className="px-5 py-4 flex items-center justify-between border-b" style={{ borderColor: 'rgba(232,146,74,0.2)', backgroundColor: 'rgba(255,255,255,0.5)' }}>
            <h3 className="font-bold text-base" style={{ color: '#C4533A' }}>Session Records</h3>
            <button onClick={() => loadRecords(activeSession?.sessionId)} disabled={!activeSession || recordsLoading} className="fdas-button fdas-button-ghost fdas-button-sm">
              Refresh
            </button>
          </div>
          <div className="overflow-auto">
            <table className="fdas-table fdas-session-table">
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
