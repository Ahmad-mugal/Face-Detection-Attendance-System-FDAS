import { useCallback, useEffect, useRef, useState } from 'react'
import Icon from './Icon'

const CHALLENGES = ['Please blink', 'Look straight at camera', 'Turn head slightly left', 'Turn head slightly right', 'Smile']

export default function CameraFrameUpload({ sessionId, onMarkRecord, isActive = false, startRequest = 0, onCameraStateChange, onCameraError, onRegisterCleanup }) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [cameraOn, setCameraOn] = useState(false)
  const [challenge, setChallenge] = useState(CHALLENGES[0])
  const [lastResult, setLastResult] = useState(null)
  const [cameraError, setCameraError] = useState('')

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOn(false)
    setLastResult(null)
    onCameraStateChange?.(false)
  }, [onCameraStateChange])

  const startCamera = useCallback(async () => {
    if (!isActive) return

    setCameraError('')
    setChallenge('Please blink')
    setLastResult(null)

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      streamRef.current = mediaStream
      if (videoRef.current) videoRef.current.srcObject = mediaStream
      setCameraOn(true)
      onCameraStateChange?.(true)
    } catch {
      stopCamera()
      setCameraError('Camera permission was denied. Please allow camera access and try again.')
      onCameraError?.()
    }
  }, [isActive, onCameraError, onCameraStateChange, stopCamera])

  useEffect(() => {
    if (!cameraOn) return undefined
    const interval = setInterval(() => {
      const results = ['recognized', 'recognized', 'recognized', 'unknown']
      const result = results[Math.floor(Math.random() * results.length)]
      setLastResult(result)
      setChallenge(CHALLENGES[Math.floor(Math.random() * CHALLENGES.length)])
      if (result === 'recognized') {
        onMarkRecord?.({
          studentName: 'Demo Student',
          rollNumber: 'DEMO-001',
          markedAt: new Date().toLocaleTimeString(),
          confidence: 0.9 + Math.random() * 0.09,
        })
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [cameraOn, onMarkRecord])

  useEffect(() => {
    if (!isActive && cameraOn) stopCamera()
  }, [isActive, cameraOn, stopCamera])

  useEffect(() => {
    if (startRequest > 0 && isActive && !cameraOn) startCamera()
  }, [startRequest, isActive, cameraOn, startCamera])

  useEffect(() => {
    onRegisterCleanup?.(stopCamera)
    return () => onRegisterCleanup?.(null)
  }, [onRegisterCleanup, stopCamera])

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
  }, [])

  return (
    <div className="rounded-xl overflow-hidden border-2 flex flex-col min-w-0" style={{ borderColor: '#FFF0E6', boxShadow: '0 0 15px rgba(232,146,74,0.3)', minHeight: 480 }}>
      <div className="px-5 py-3 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 border-b" style={{ backgroundColor: '#FFF0E6', borderColor: '#E8924A' }}>
        <div>
          <h2 className="font-bold text-base" style={{ color: '#C4533A' }}>Live Attendance Mode</h2>
          {sessionId && <p className="text-xs mt-0.5" style={{ color: '#887369' }}>Session #{sessionId}</p>}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="px-3 py-1 rounded-full text-xs font-bold" style={{ backgroundColor: isActive ? '#d1fae5' : '#ffdad6', color: isActive ? '#065f46' : '#93000a' }}>
            {isActive ? 'Session Active' : 'Session Inactive'}
          </span>
          {cameraOn && (
            <div className="flex items-center gap-2 px-3 py-1 rounded-full" style={{ backgroundColor: '#FFF0E6' }}>
              <div className="w-2.5 h-2.5 rounded-full animate-blink" style={{ backgroundColor: '#E8924A' }} />
              <span className="text-xs font-bold uppercase tracking-wider" style={{ color: '#D4A017' }}>Camera Active</span>
            </div>
          )}
        </div>
      </div>

      <div className="relative flex-1 bg-black overflow-hidden" style={{ minHeight: 360 }}>
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="absolute inset-0 h-full w-full object-cover"
          style={{ display: cameraOn ? 'block' : 'none' }}
        />

        {!cameraOn ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-8">
            <Icon name="videocam_off" size={80} style={{ color: '#55433b' }} />
            <p className="mt-3 font-semibold text-sm" style={{ color: '#887369' }}>{cameraError || 'Click "Start Attendance" to begin'}</p>
          </div>
        ) : null}

        {cameraOn && lastResult === 'recognized' && (
          <div className="absolute border-2 rounded-lg" style={{ top: '20%', left: '30%', width: 180, height: 220, maxWidth: '45%', borderColor: '#E8924A', boxShadow: '0 0 15px rgba(232,146,74,0.5)' }}>
            <div className="absolute -top-3 -right-3 w-6 h-6 rounded-full flex items-center justify-center text-white" style={{ backgroundColor: '#D4A017' }}>
              <Icon name="check" size={14} />
            </div>
            <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-white text-xs font-bold whitespace-nowrap" style={{ backgroundColor: '#D4A017' }}>
              Demo Student - DEMO-001
            </div>
          </div>
        )}

        {cameraOn && lastResult === 'unknown' && (
          <div className="absolute border-2 border-dashed rounded-lg" style={{ top: '20%', left: '30%', width: 160, height: 200, maxWidth: '45%', borderColor: '#FFF0E6' }}>
            <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-white text-[10px] font-bold whitespace-nowrap" style={{ backgroundColor: '#C4533A' }}>
              Please Register First
            </div>
          </div>
        )}

        {cameraOn && (
          <>
            <div className="absolute bottom-4 left-4 right-4 py-2 px-4 rounded-xl text-center font-bold text-sm" style={{ backgroundColor: 'rgba(196,83,58,0.85)', color: '#fff', backdropFilter: 'blur(4px)' }}>
              <Icon name="psychology" size={16} className="mr-1" />
              Liveness Check: {challenge}
            </div>
            <div className="absolute top-4 left-4 py-1.5 px-3 rounded-full text-xs font-semibold flex items-center gap-1" style={{ backgroundColor: 'rgba(196,83,58,0.8)', color: '#fff', backdropFilter: 'blur(4px)' }}>
              <Icon name="location_on" size={14} />
              CS Dept | BSCS-2022
            </div>
          </>
        )}
      </div>

      <div className="px-5 py-3 flex items-center justify-between" style={{ backgroundColor: '#FFF0E6', borderTop: '1px solid rgba(232,146,74,0.2)' }}>
        <div className="flex items-center gap-2 text-sm" style={{ color: '#887369' }}>
          <Icon name="videocam" size={18} style={{ color: '#E8924A' }} />
          Cam 01 - Main Lab
        </div>
        <div className="text-sm font-bold" style={{ color: cameraOn ? '#C4533A' : '#887369' }}>
          {cameraOn ? 'Scanning...' : 'Stopped'}
        </div>
      </div>
    </div>
  )
}
