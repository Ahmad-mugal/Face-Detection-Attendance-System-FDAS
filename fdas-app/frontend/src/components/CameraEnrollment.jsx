import { useState } from 'react'
import Icon from './Icon'

const SAMPLE_COLORS = ['#C4533A', '#D4A017', '#E8924A']

export default function CameraEnrollment({ onCapture }) {
  const [cameraActive, setCameraActive] = useState(false)
  const [captured, setCaptured] = useState([])

  const startCamera = () => setCameraActive(true)

  const captureSample = () => {
    if (!cameraActive || captured.length >= 3) return
    const next = [...captured, { id: captured.length + 1, color: SAMPLE_COLORS[captured.length] }]
    setCaptured(next)
    onCapture?.(next)
    if (next.length === 3) setCameraActive(false)
  }

  const retakeSamples = () => {
    setCaptured([])
    setCameraActive(false)
    onCapture?.([])
  }

  return (
    <div className="rounded-xl border-2 overflow-hidden fdas-card" style={{ borderColor: '#dbc1b7' }}>
      <div className="px-5 py-4 border-b flex items-start justify-between gap-4" style={{ borderColor: '#f0dfd8' }}>
        <div>
          <h4 className="font-bold text-sm" style={{ color: '#4A2B0F' }}>Face Enrollment</h4>
          <p className="text-xs mt-0.5" style={{ color: '#887369' }}>
            Static Phase 1 preview. Capture 3 dummy face samples.
          </p>
        </div>
        <span className="px-2.5 py-1 rounded-full text-xs font-bold whitespace-nowrap" style={{ backgroundColor: '#FFF0E6', color: '#C4533A' }}>
          {captured.length}/3 samples
        </span>
      </div>

      <div className="relative flex items-center justify-center min-h-[240px]" style={{ backgroundColor: '#221a16' }}>
        <div className="absolute inset-4 rounded-xl border-2 border-dashed" style={{ borderColor: cameraActive ? '#D4A017' : '#55433b' }} />
        <div className="text-center p-8 relative z-10">
          <Icon name={cameraActive ? 'center_focus_strong' : 'videocam'} size={64} className="block mx-auto mb-3" style={{ color: cameraActive ? '#D4A017' : '#887369' }} />
          <p className="text-sm font-bold" style={{ color: cameraActive ? '#fff8f6' : '#887369' }}>
            {cameraActive ? 'Camera preview placeholder active' : 'Camera preview placeholder'}
          </p>
          <p className="text-xs mt-1" style={{ color: '#dbc1b7' }}>No backend upload or recognition in Phase 1.1</p>
        </div>
        {cameraActive && (
          <div className="absolute left-8 right-8 top-1/2 h-0.5 animate-scan" style={{ backgroundColor: 'rgba(212,160,23,0.7)' }} />
        )}
      </div>

      <div className="grid grid-cols-3 gap-3 p-4" style={{ backgroundColor: '#FFF0E6' }}>
        {[0, 1, 2].map(index => {
          const sample = captured[index]
          return (
            <div key={index} className="aspect-[4/3] rounded-xl border-2 flex flex-col items-center justify-center gap-1" style={{ backgroundColor: '#fff8f6', borderColor: sample ? sample.color : '#dbc1b7' }}>
              {sample ? (
                <>
                  <Icon name="face" size={28} style={{ color: sample.color }} />
                  <span className="text-[11px] font-bold" style={{ color: '#4A2B0F' }}>Sample {index + 1}</span>
                </>
              ) : (
                <>
                  <Icon name="add_a_photo" size={24} style={{ color: '#887369' }} />
                  <span className="text-[11px] font-semibold" style={{ color: '#887369' }}>Empty slot</span>
                </>
              )}
            </div>
          )
        })}
      </div>

      <div className="p-4 flex flex-col sm:flex-row gap-3">
        <button
          type="button"
          onClick={startCamera}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg font-bold text-sm transition-all active:scale-95"
          style={{ backgroundColor: '#C4533A', color: '#fff' }}
        >
          <Icon name="videocam" size={18} />
          Start Camera
        </button>
        <button
          type="button"
          onClick={captureSample}
          disabled={!cameraActive || captured.length === 3}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg font-bold text-sm transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ backgroundColor: '#D4A017', color: '#fff' }}
        >
          <Icon name="photo_camera" size={18} />
          Capture Face Sample
        </button>
        <button
          type="button"
          onClick={retakeSamples}
          className="flex-1 py-2.5 rounded-lg font-semibold text-sm border transition-all"
          style={{ borderColor: '#C4533A', color: '#C4533A' }}
        >
          Retake Samples
        </button>
      </div>
    </div>
  )
}
