import { useCallback, useEffect, useRef, useState } from 'react'
import { getApiError } from '../api/client'
import { studentsApi } from '../api/studentsApi'
import {
  FACE_ENROLLMENT_CAPTURE_INTERVAL_MS,
  FACE_ENROLLMENT_COUNTDOWN_SECONDS,
  FACE_ENROLLMENT_SAMPLE_COUNT,
} from '../constants/faceEnrollment'
import Icon from './Icon'

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

export default function AutoFaceEnrollmentCapture({ studentId, studentName, onCompleted }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const cancelledRef = useRef(false)
  const [status, setStatus] = useState('idle')
  const [countdown, setCountdown] = useState(FACE_ENROLLMENT_COUNTDOWN_SECONDS)
  const [capturedCount, setCapturedCount] = useState(0)
  const [capturedSamples, setCapturedSamples] = useState([])
  const [savedSampleCount, setSavedSampleCount] = useState(0)
  const [error, setError] = useState('')

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
      if (!['starting', 'countdown', 'capturing', 'uploading'].includes(status)) return
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
    if (!studentId || samples.length !== FACE_ENROLLMENT_SAMPLE_COUNT) return
    setStatus('uploading')
    setError('')
    try {
      const result = await studentsApi.uploadFaceEnrollment(studentId, samples)
      const savedCount = result.uploadedSamples?.length || 0
      setSavedSampleCount(savedCount)
      setStatus('complete')
      onCompleted?.(result)
    } catch (err) {
      setStatus('error')
      setError(getApiError(err, 'Unable to upload face enrollment samples.'))
    }
  }, [onCompleted, studentId])

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

      setStatus('countdown')
      for (let seconds = FACE_ENROLLMENT_COUNTDOWN_SECONDS; seconds > 0; seconds -= 1) {
        if (cancelledRef.current) return
        setCountdown(seconds)
        await sleep(1000)
      }

      const samples = []
      setStatus('capturing')
      for (let index = 0; index < FACE_ENROLLMENT_SAMPLE_COUNT; index += 1) {
        if (cancelledRef.current) return
        const sample = await captureFrame()
        samples.push(sample)
        setCapturedCount(samples.length)
        if (samples.length < FACE_ENROLLMENT_SAMPLE_COUNT) await sleep(FACE_ENROLLMENT_CAPTURE_INTERVAL_MS)
      }

      setCapturedSamples(samples)
      stopCamera()
      await uploadSamples(samples)
    } catch (err) {
      stopCamera()
      setStatus('error')
      setError(getApiError(err, 'Unable to start camera or capture samples.'))
    }
  }, [captureFrame, clearTemporarySamples, stopCamera, studentId, uploadSamples])

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

  const active = ['starting', 'countdown', 'capturing', 'uploading'].includes(status)
  const progressLabel = status === 'capturing'
    ? `Capturing ${capturedCount}/${FACE_ENROLLMENT_SAMPLE_COUNT}`
    : `${capturedCount}/${FACE_ENROLLMENT_SAMPLE_COUNT} samples`

  return (
    <div className="rounded-xl border-2 overflow-hidden fdas-card" style={{ borderColor: '#dbc1b7' }}>
      <div className="px-5 py-4 border-b flex items-start justify-between gap-4" style={{ borderColor: '#f0dfd8' }}>
        <div>
          <h4 className="font-bold text-sm" style={{ color: '#4A2B0F' }}>Face Enrollment</h4>
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
        {status === 'countdown' && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/45">
            <span className="text-7xl font-black text-white">{countdown}</span>
          </div>
        )}
      </div>

      <div className="p-4 space-y-3" style={{ backgroundColor: '#FFF0E6' }}>
        <div className="rounded-lg border p-3 text-xs leading-5" style={{ backgroundColor: '#fff8f6', borderColor: '#f0dfd8', color: '#55433b' }}>
          <p>Keep your face inside the frame</p>
          <p>Slowly move face slightly left and right</p>
          <p>Keep normal expression</p>
        </div>

        {status === 'uploading' && <p className="text-sm font-bold" style={{ color: '#C4533A' }}>Uploading {FACE_ENROLLMENT_SAMPLE_COUNT} samples...</p>}
        {status === 'complete' && <p className="text-sm font-bold" style={{ color: '#15803d' }}>Face enrollment completed. Saved samples: {savedSampleCount}</p>}
        {error && <p className="text-sm font-bold" style={{ color: '#93000a' }}>{error}</p>}

        <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: '#f0dfd8' }}>
          <div
            className="h-full transition-all"
            style={{ width: `${(capturedCount / FACE_ENROLLMENT_SAMPLE_COUNT) * 100}%`, backgroundColor: '#C4533A' }}
          />
        </div>
      </div>

      <div className="p-4 flex flex-col sm:flex-row gap-3">
        <button
          type="button"
          onClick={startRegistration}
          disabled={!studentId || active}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg font-bold text-sm transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ backgroundColor: '#C4533A', color: '#fff' }}
        >
          <Icon name="videocam" size={18} />
          Start Face Registration
        </button>
        {status === 'error' && capturedSamples.length === FACE_ENROLLMENT_SAMPLE_COUNT && (
          <button
            type="button"
            onClick={retryUpload}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg font-bold text-sm transition-all active:scale-95"
            style={{ backgroundColor: '#D4A017', color: '#fff' }}
          >
            <Icon name="upload" size={18} />
            Retry Upload
          </button>
        )}
        <button
          type="button"
          onClick={cancelRegistration}
          disabled={!active && capturedSamples.length === 0}
          className="flex-1 py-2.5 rounded-lg font-semibold text-sm border transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ borderColor: '#C4533A', color: '#C4533A' }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
