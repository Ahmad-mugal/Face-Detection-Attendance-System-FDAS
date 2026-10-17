import { mirroredFaceBoxX } from '../utils/faceTracking'

const FACE_STYLES = {
  AttendanceMarked: { color: '#22c55e', label: 'Attendance Marked Successfully' },
  AlreadyMarked: { color: '#38bdf8', label: 'Already Marked Present' },
  RecognitionReady: { color: '#facc15', label: 'Processing' },
  Unknown: { color: '#fb923c', label: 'Unrecognized' },
  Ambiguous: { color: '#f59e0b', label: 'Ambiguous' },
  IdentityConflict: { color: '#f59e0b', label: 'Identity conflict' },
  NotEligible: { color: '#f97316', label: 'Not eligible' },
  PoorFaceQuality: { color: '#facc15', label: 'Hold still / Improve image quality' },
  InvalidEmbedding: { color: '#ef4444', label: 'Unable to process' },
  PersistenceError: { color: '#ef4444', label: 'Not recorded' },
}

function facePresentation(face) {
  const style = FACE_STYLES[face.status] || { color: '#facc15', label: 'Detected' }
  const identity = face.studentName
    ? `${face.studentName}${face.rollNo ? ` (${face.rollNo})` : ''}`
    : null
  return { ...style, label: identity ? `${identity} · ${style.label}` : style.label }
}

export default function FaceOverlay({ faces, sourceWidth, sourceHeight, mirrored = true }) {
  if (!sourceWidth || !sourceHeight || !faces?.length) return null
  const strokeWidth = Math.max(2, sourceWidth / 320)
  const fontSize = Math.max(13, sourceWidth / 42)

  return (
    <>
      <svg
        data-face-overlay
        className="pointer-events-none absolute inset-0 z-[2] h-full w-full"
        viewBox={`0 0 ${sourceWidth} ${sourceHeight}`}
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        {faces.map(face => {
          const { bbox } = face
          const presentation = facePresentation(face)
          const x = mirroredFaceBoxX(bbox, sourceWidth, mirrored)
          const labelWidth = Math.min(
            Math.max(bbox.width, presentation.label.length * fontSize * 0.58 + 18),
            sourceWidth - x,
          )
          const labelHeight = fontSize + 12
          const labelTier = (Math.max(1, face.faceIndex || 1) - 1) % 3
          const labelY = Math.max(0, bbox.y - (labelHeight * (labelTier + 1)))
          return (
            <g key={face.trackId || face.faceId}>
              <rect
                data-face-box={face.trackId || face.faceId}
                data-face-status={face.status}
                x={x}
                y={bbox.y}
                width={bbox.width}
                height={bbox.height}
                fill="none"
                stroke={presentation.color}
                strokeWidth={strokeWidth}
                rx={Math.max(3, strokeWidth)}
                vectorEffect="non-scaling-stroke"
              />
              <rect
                x={x}
                y={labelY}
                width={labelWidth}
                height={labelHeight}
                fill="rgba(24, 18, 15, 0.88)"
                rx="4"
              />
              <text
                x={x + 8}
                y={labelY + fontSize + 3}
                fill="#fff"
                fontSize={fontSize}
                fontWeight="700"
                fontFamily="system-ui, sans-serif"
              >
                {presentation.label}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="sr-only" aria-live="polite">
        {faces.map(face => `${facePresentation(face).label}.`).join(' ')}
      </div>
    </>
  )
}
