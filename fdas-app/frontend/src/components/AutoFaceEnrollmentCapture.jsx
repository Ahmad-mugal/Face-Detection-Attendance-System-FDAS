import { useCallback, useEffect, useRef, useState } from 'react'
import { getApiError } from '../api/client'
import { faceMatchingApi } from '../api/faceMatchingApi'
import { studentsApi } from '../api/studentsApi'
import {
  FACE_ENROLLMENT_CAPTURE_INTERVAL_MS,
  FACE_ENROLLMENT_SAMPLE_COUNT,
} from '../constants/faceEnrollment'
import Icon from './Icon'

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
const SINGLE_FACE_STABLE_MS = 1000
const SINGLE_FACE_POLL_MS = 250
const RECOVERY_CAPTURE_INTERVAL_MS = 700
const RECOVERY_VARIATIONS = [
  'Look straight at the camera',
  'Turn slightly left',
  'Turn slightly right',
  'Move slightly closer',
  'Move slightly farther',
  'Return to a normal front view',
  'Tilt your head slightly upward',
  'Tilt your head slightly downward',
]

export default function AutoFaceEnrollmentCapture({ studentId, studentName, onCompleted, recoveryMode = false }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const cancelledRef = useRef(false)
  const [status, setStatus] = useState('idle')
  const [capturedCount, setCapturedCount] = useState(0)
  const [capturedSamples, setCapturedSamples] = useState([])
  const [savedSampleCount, setSavedSampleCount] = useState(0)
  const [error, setError] = useState('')
  const [readiness, setReadiness] = useState(null)
  const [targetCount, setTargetCount] = useState(FACE_ENROLLMENT_SAMPLE_COUNT)
  const [faceGuard, setFaceGuard] = useState({
    status: 'Unchecked',
    message: 'No face detected.',
    ready: false,
  })

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  const clearTemporarySamples = useCallback(() => {
    setCapturedSamples([])
    setCapturedCount(0)
    setSavedSampleCount(0)
  }, [])

  useEffect(() => {
    const handleBeforeUnload = event => {
      if (!['starting', 'stabilizing', 'capturing', 'paused', 'uploading'].includes(status)) return
      event.preventDefault()
      event.returnValue = 'Face registration is active. Leaving will stop the camera and discard unsaved samples.'
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [status])

  useEffect(() => () => {
    cancelledRef.current = true
    stopCamera()
  }, [stopCamera])

  useEffect(() => {
    let active = true
    if (!recoveryMode || !studentId) {
      setReadiness(null)
      setTargetCount(FACE_ENROLLMENT_SAMPLE_COUNT)
      return () => { active = false }
    }
    studentsApi.getDeepEnrollmentReadiness(studentId)
      .then(result => {
        if (!active) return
        setReadiness(result)
        const deficit = Math.max(0, result.additionalNeeded || 0)
        setTargetCount(Math.min(FACE_ENROLLMENT_SAMPLE_COUNT, Math.max(deficit, 8)))
      })
      .catch(err => {
        if (active) setError(getApiError(err, 'Unable to load deep enrollment readiness.'))
      })
    return () => { active = false }
  }, [recoveryMode, studentId])

  const sampleCount = recoveryMode ? targetCount : FACE_ENROLLMENT_SAMPLE_COUNT

  const captureFrame = useCallback(() => new Promise((resolve, reject) => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
      reject(new Error('Camera frame is not ready yet.'))
      return
    }

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob(blob => {
      if (!blob) {
        reject(new Error('Unable to capture camera frame.'))
        return
      }
      resolve(new File([blob], `face_sample_${Date.now()}.jpg`, { type: 'image/jpeg' }))
    }, 'image/jpeg', 0.9)
  }), [])

  const uploadSamples = useCallback(async samples => {
    if (!studentId || samples.length !== sampleCount) return
    setStatus('uploading')
    setError('')
    try {
      const result = recoveryMode
        ? await studentsApi.uploadDeepRecovery(studentId, samples)
        : await studentsApi.uploadFaceEnrollment(studentId, samples)
      const savedCount = recoveryMode
        ? result.recoverySamples?.length || 0
        : result.uploadedSamples?.length || 0
      setSavedSampleCount(savedCount)
      if (recoveryMode) setReadiness(current => ({
        ...current,
        validDeepEmbeddings: result.deepCountAfter,
        additionalNeeded: result.additionalNeeded,
        readiness: result.readiness,
      }))
      setStatus('complete')
      onCompleted?.(result)
    } catch (err) {
      setStatus('error')
      const detail = err?.response?.data?.detail
      setError(detail?.message || getApiError(err, 'Unable to upload face enrollment samples.'))
    }
  }, [onCompleted, recoveryMode, sampleCount, studentId])

  const inspectSingleFace = useCallback(async (sample, referenceFile = null) => {
    const basicResult = await faceMatchingApi.validateSingleFace({ file: sample, referenceFile })
    let result = basicResult
    if (recoveryMode && basicResult.ready && basicResult.faceCount === 1 && basicResult.continuityPassed !== false) {
      const deepResult = await studentsApi.validateDeepRecoverySample(sample)
      result = {
        ...basicResult,
        ready: deepResult.success,
        message: deepResult.success ? 'Face detected — deep-ready.' : deepResult.message,
        deepStatus: deepResult.status,
        deepFaceCount: deepResult.deepFaceCount,
      }
    }
    setFaceGuard(result)
    return result
  }, [recoveryMode])

  const waitForStableSingleFace = useCallback(async (referenceFile = null) => {
    let stableSince = null
    while (!cancelledRef.current) {
      const sample = await captureFrame()
      const result = await inspectSingleFace(sample, referenceFile)
      if (result.ready && result.faceCount === 1) {
        if (stableSince === null) stableSince = Date.now()
        if (Date.now() - stableSince >= SINGLE_FACE_STABLE_MS) return sample
      } else {
        stableSince = null
        setStatus('paused')
      }
      await sleep(SINGLE_FACE_POLL_MS)
    }
    return null
  }, [captureFrame, inspectSingleFace])

  const startRegistration = useCallback(async () => {
    if (!studentId) {
      setError('Save the student profile before starting face registration.')
      return
    }

    cancelledRef.current = false
    setStatus('starting')
    setError('')
    clearTemporarySamples()

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      if (cancelledRef.current) {
        stream.getTracks().forEach(track => track.stop())
        return
      }
      streamRef.current = stream
      videoRef.current.srcObject = stream
      await videoRef.current.play()

      setStatus('stabilizing')
      const lockSample = await waitForStableSingleFace()
      if (!lockSample || cancelledRef.current) return

      const samples = [lockSample]
      setCapturedCount(1)
      setStatus('capturing')
      while (samples.length < sampleCount) {
        if (cancelledRef.current) return
        await sleep(recoveryMode ? RECOVERY_CAPTURE_INTERVAL_MS : FACE_ENROLLMENT_CAPTURE_INTERVAL_MS)
        if (cancelledRef.current) return
        const candidate = await captureFrame()
        const validation = await inspectSingleFace(candidate, lockSample)
        if (!validation.ready || validation.faceCount !== 1 || validation.continuityPassed === false) {
          setStatus('paused')
          const resumedSample = await waitForStableSingleFace(lockSample)
          if (!resumedSample || cancelledRef.current) return
          samples.push(resumedSample)
          setStatus('capturing')
        } else {
          samples.push(candidate)
        }
        setCapturedCount(samples.length)
      }

      setCapturedSamples(samples)
      stopCamera()
      await uploadSamples(samples)
    } catch (err) {
      stopCamera()
      setStatus('error')
      setError(getApiError(err, 'Unable to start camera or capture samples.'))
    }
  }, [captureFrame, clearTemporarySamples, inspectSingleFace, recoveryMode, sampleCount, stopCamera, studentId, uploadSamples, waitForStableSingleFace])

  const cancelRegistration = useCallback(() => {
    cancelledRef.current = true
    stopCamera()
    clearTemporarySamples()
    setError('')
    setStatus('idle')
  }, [clearTemporarySamples, stopCamera])

  const retryUpload = useCallback(() => {
    uploadSamples(capturedSamples)
  }, [capturedSamples, uploadSamples])

  const active = ['starting', 'stabilizing', 'capturing', 'paused', 'uploading'].includes(status)
  const progressLabel = status === 'capturing'
    ? `Capturing ${capturedCount}/${sampleCount}`
    : `${capturedCount}/${sampleCount} samples`
  const variationIndex = Math.min(
    RECOVERY_VARIATIONS.length - 1,
    Math.floor((capturedCount / Math.max(sampleCount, 1)) * RECOVERY_VARIATIONS.length),
  )

  return (
    <div className="rounded-xl border-2 overflow-hidden fdas-card" style={{ borderColor: '#dbc1b7' }}>
      <div className="px-5 py-4 border-b flex items-start justify-between gap-4" style={{ borderColor: '#f0dfd8' }}>
        <div>
          <h4 className="font-bold text-sm" style={{ color: '#4A2B0F' }}>{recoveryMode ? 'Deep Enrollment Recovery' : 'Face Enrollment'}</h4>
          <p className="text-xs mt-0.5" style={{ color: '#887369' }}>
            {studentId ? `Ready for ${studentName || 'saved student'}` : 'Save the student profile before registration.'}
          </p>
        </div>
        <span className="px-2.5 py-1 rounded-full text-xs font-bold whitespace-nowrap" style={{ backgroundColor: '#FFF0E6', color: '#C4533A' }}>
          {progressLabel}
        </span>
      </div>

      <div className="relative flex items-center justify-center min-h-[240px]" style={{ backgroundColor: '#221a16' }}>
        <video ref={videoRef} className="absolute inset-0 h-full w-full object-cover" muted playsInline />
        <canvas ref={canvasRef} className="hidden" />
        <div className="absolute inset-4 rounded-xl border-2 border-dashed pointer-events-none" style={{ borderColor: active ? '#D4A017' : '#55433b' }} />
        {!streamRef.current && (
          <div className="text-center p-8 relative z-10">
            <Icon name={status === 'complete' ? 'check_circle' : 'videocam'} size={64} className="block mx-auto mb-3" style={{ color: status === 'complete' ? '#15803d' : '#887369' }} />
            <p className="text-sm font-bold" style={{ color: status === 'complete' ? '#dcfce7' : '#887369' }}>
              {status === 'complete' ? 'Capturing complete' : 'Camera preview'}
            </p>
          </div>
        )}
        {['stabilizing', 'paused'].includes(status) && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/45">
            <span className="max-w-md px-6 text-center text-lg font-black text-white">{faceGuard.message}</span>
          </div>
        )}
      </div>

      <div className="p-4 space-y-3" style={{ backgroundColor: '#FFF0E6' }}>
        <div className="rounded-lg border p-3 text-xs leading-5" style={{ backgroundColor: '#fff8f6', borderColor: '#f0dfd8', color: '#55433b' }}>
          <p>Keep your face inside the frame</p>
          <p>Slowly move face slightly left and right</p>
          <p>Keep normal expression</p>
          {recoveryMode && <p>Use small natural distance, vertical-head, and modest lighting variations. Avoid extreme side profiles.</p>}
          {recoveryMode && <p className="font-bold" style={{ color: '#934619' }}>Current variation: {RECOVERY_VARIATIONS[variationIndex]}</p>}
          <p className="font-bold" style={{ color: faceGuard.ready ? '#15803d' : '#93000a' }}>{faceGuard.message}</p>
          <p>Capture starts or resumes after one face remains stable for approximately one second.</p>
          {recoveryMode && <p>Every counted sample must also pass the local deep detector. Historical samples remain unchanged.</p>}
        </div>

        {recoveryMode && readiness && (
          <div className="rounded-lg border p-3 text-xs" style={{ backgroundColor: '#fff', borderColor: '#dbc1b7', color: '#55433b' }}>
            <p><strong>Current deep embeddings:</strong> {readiness.validDeepEmbeddings}/{readiness.requiredMinimum}</p>
            <p><strong>Readiness:</strong> {readiness.readiness}</p>
            {readiness.additionalNeeded > 0 && (
              <label className="block mt-2">
                <span className="font-bold">Recovery samples for this batch</span>
                <input
                  type="number"
                  min={Math.max(1, readiness.additionalNeeded)}
                  max={FACE_ENROLLMENT_SAMPLE_COUNT}
                  value={targetCount}
                  disabled={active}
                  onChange={event => setTargetCount(Math.min(FACE_ENROLLMENT_SAMPLE_COUNT, Math.max(readiness.additionalNeeded, Number(event.target.value) || readiness.additionalNeeded)))}
                  className="ml-2 w-20 rounded border px-2 py-1"
                  style={{ borderColor: '#dbc1b7' }}
                />
              </label>
            )}
          </div>
        )}

        {status === 'uploading' && <p className="text-sm font-bold" style={{ color: '#C4533A' }}>Uploading {sampleCount} samples...</p>}
        {status === 'complete' && <p className="text-sm font-bold" style={{ color: '#15803d' }}>{recoveryMode ? 'Deep recovery completed' : 'Face enrollment completed'}. Saved samples: {savedSampleCount}</p>}
        {error && <p className="text-sm font-bold" style={{ color: '#93000a' }}>{error}</p>}

        <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: '#f0dfd8' }}>
          <div
            className="h-full transition-all"
            style={{ width: `${(capturedCount / sampleCount) * 100}%`, backgroundColor: '#C4533A' }}
          />
        </div>
      </div>

      <div className="p-4 flex flex-col sm:flex-row gap-3">
        <button
          type="button"
          onClick={startRegistration}
          disabled={!studentId || active || (recoveryMode && (!readiness || readiness.additionalNeeded === 0))}
          className="fdas-button fdas-button-primary flex-1"
        >
          <Icon name="videocam" size={18} />
          {recoveryMode ? 'Start Deep Recovery' : 'Start Face Registration'}
        </button>
        {status === 'error' && capturedSamples.length === sampleCount && (
          <button
            type="button"
            onClick={retryUpload}
            className="fdas-button fdas-button-warning flex-1"
          >
            <Icon name="upload" size={18} />
            Retry Upload
          </button>
        )}
        <button
          type="button"
          onClick={cancelRegistration}
          disabled={!active && capturedSamples.length === 0}
          className="fdas-button fdas-button-outline flex-1"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
