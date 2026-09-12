import { useCallback, useEffect, useRef, useState } from 'react'
import { faceMatchingApi } from '../api/faceMatchingApi'
import { getApiError } from '../api/client'

const QUERY_PROMPTS = [
  'Frontal — look naturally at the camera.',
  'Frontal repeat — relax, then look at the camera again.',
  'Turn your face slightly left.',
  'Turn your face slightly right.',
  'Move slightly closer to the camera.',
  'Move slightly farther from the camera.',
  'Use a small upward face angle.',
  'Use a small downward face angle.',
  'Make a modest, normal lighting variation.',
  'Neutral final capture.',
]

const COUNTED_STATUSES = new Set(['DiagnosticMatched', 'MatchBelowThreshold', 'AmbiguousMatch'])

function formatScore(value) {
  return typeof value === 'number' ? value.toFixed(6) : '—'
}

function captureFile(video, canvas) {
  const width = video.videoWidth || 640
  const height = video.videoHeight || 480
  canvas.width = width
  canvas.height = height
  canvas.getContext('2d').drawImage(video, 0, 0, width, height)
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (!blob) {
        reject(new Error('The webcam frame could not be captured.'))
        return
      }
      resolve(new File([blob], `phase10_7d_query_${Date.now()}.jpg`, { type: 'image/jpeg' }))
    }, 'image/jpeg', 0.92)
  })
}

export default function DeepRecognitionDiagnosticCapture({ student, onCompleted }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const referenceFileRef = useRef(null)
  const [cameraActive, setCameraActive] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('Start the camera when Student #22 is the only person in frame.')
  const [error, setError] = useState('')
  const [results, setResults] = useState([])
  const [copied, setCopied] = useState(false)

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    referenceFileRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraActive(false)
  }, [])

  useEffect(() => stopCamera, [stopCamera])

  const startCamera = async () => {
    setError('')
    setCopied(false)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: false,
      })
      streamRef.current = stream
      videoRef.current.srcObject = stream
      await videoRef.current.play()
      setCameraActive(true)
      setMessage('Face detected state will be verified when you capture each query.')
    } catch (err) {
      setError(err?.message || 'Unable to start the webcam.')
    }
  }

  const captureQuery = async () => {
    if (!cameraActive || busy || results.length >= QUERY_PROMPTS.length) return
    setBusy(true)
    setError('')
    setCopied(false)
    try {
      const queryFile = await captureFile(videoRef.current, canvasRef.current)
      const singleFace = await faceMatchingApi.validateSingleFace({
        file: queryFile,
        referenceFile: referenceFileRef.current,
      })
      if (!singleFace.ready || singleFace.faceCount !== 1) {
        setMessage(singleFace.message || 'Exactly one continuous face is required. This query was not counted.')
        return
      }

      const diagnostic = await faceMatchingApi.diagnoseDeep({
        departmentId: student.departmentId,
        expectedStudentId: student.studentId,
        file: queryFile,
      })
      if (!COUNTED_STATUSES.has(diagnostic.status)) {
        setMessage(`${diagnostic.message || diagnostic.status} This query was not counted; please retry the same prompt.`)
        return
      }

      if (!referenceFileRef.current) referenceFileRef.current = queryFile
      const nextResults = [...results, {
        query: results.length + 1,
        variation: QUERY_PROMPTS[results.length],
        expectedStudentScore: diagnostic.expectedStudentScore,
        topCandidate: diagnostic.topCandidate,
        secondCandidate: diagnostic.secondCandidate,
        scoreMargin: diagnostic.scoreMargin,
        topAboveThreshold: diagnostic.topAboveThreshold,
        marginPassed: diagnostic.marginPassed,
        status: diagnostic.status,
        matched: diagnostic.matched,
        thresholdUsed: diagnostic.thresholdUsed,
        requiredMargin: diagnostic.requiredMargin,
        scoringMethod: diagnostic.scoringMethod,
        attendanceCreated: diagnostic.attendanceCreated,
        persistentWrite: diagnostic.persistentWrite,
      }]
      setResults(nextResults)
      if (nextResults.length === QUERY_PROMPTS.length) {
        setMessage('All 10 independent queries are complete. Query images have been discarded; copy the metadata report below.')
        stopCamera()
        onCompleted?.(nextResults)
      } else {
        setMessage(`Query ${nextResults.length} recorded. Prepare for query ${nextResults.length + 1}.`)
      }
    } catch (err) {
      setError(getApiError(err, err?.message || 'Unable to run this diagnostic query.'))
    } finally {
      setBusy(false)
    }
  }

  const copyReport = async () => {
    const report = {
      phase: '10.7D',
      studentId: student.studentId,
      rollNumber: student.rollNumber,
      queryCount: results.length,
      imagesPersisted: false,
      results,
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2))
      setCopied(true)
    } catch {
      setError('Clipboard access was unavailable. Select and copy the visible result rows instead.')
    }
  }

  const nextPrompt = QUERY_PROMPTS[results.length]

  return (
    <div className="space-y-4">
      <div className="rounded-xl border p-4 text-sm" style={{ backgroundColor: '#fff8e8', borderColor: '#e4bd55', color: '#5f4300' }}>
        <strong>Diagnostic-only safety mode:</strong> exactly 10 independent query frames are evaluated one at a time. Images are not saved as templates, embeddings, recovery samples, or attendance evidence.
      </div>

      <div className="rounded-xl overflow-hidden border" style={{ borderColor: '#dbc1b7', backgroundColor: '#23170f' }}>
        <video ref={videoRef} muted playsInline className="block w-full aspect-video object-cover" />
        <canvas ref={canvasRef} className="hidden" />
      </div>

      <div className="rounded-xl border p-4" style={{ borderColor: '#f0dfd8', backgroundColor: '#fff8f6' }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-wide" style={{ color: '#934619' }}>Progress: {results.length}/10</p>
            <p className="mt-1 font-bold" style={{ color: '#4A2B0F' }}>{nextPrompt || 'Capture set complete.'}</p>
          </div>
          <div className="flex gap-2">
            {!cameraActive && results.length < 10 && <button onClick={startCamera} className="rounded-lg px-4 py-2 font-bold text-white" style={{ backgroundColor: '#C4533A' }}>Start Camera</button>}
            {cameraActive && <button onClick={stopCamera} disabled={busy} className="rounded-lg border px-4 py-2 font-bold disabled:opacity-60" style={{ borderColor: '#C4533A', color: '#C4533A' }}>Stop Camera</button>}
            <button onClick={captureQuery} disabled={!cameraActive || busy || results.length >= 10} className="rounded-lg px-4 py-2 font-bold text-white disabled:opacity-50" style={{ backgroundColor: '#0f766e' }}>{busy ? 'Checking…' : `Capture Query ${results.length + 1}`}</button>
          </div>
        </div>
        <p className="mt-3 text-sm" style={{ color: '#55433b' }}>{message}</p>
        {error && <p className="mt-2 rounded-lg px-3 py-2 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', color: '#93000a' }}>{error}</p>}
      </div>

      {results.length > 0 && (
        <div className="rounded-xl border overflow-x-auto" style={{ borderColor: '#f0dfd8' }}>
          <div className="flex items-center justify-between gap-3 p-3" style={{ backgroundColor: '#fff1eb' }}>
            <strong style={{ color: '#4A2B0F' }}>Transient result metadata</strong>
            <button onClick={copyReport} className="rounded-lg border px-3 py-1.5 text-sm font-bold" style={{ borderColor: '#934619', color: '#934619' }}>{copied ? 'Copied' : 'Copy JSON report'}</button>
          </div>
          <table className="min-w-full text-xs">
            <thead><tr style={{ color: '#934619' }}><th className="p-2 text-left">#</th><th className="p-2 text-left">Variation</th><th className="p-2 text-left">#22 score</th><th className="p-2 text-left">Top</th><th className="p-2 text-left">Second distinct</th><th className="p-2 text-left">Margin</th><th className="p-2 text-left">Classification</th></tr></thead>
            <tbody>{results.map(item => <tr key={item.query} className="border-t" style={{ borderColor: '#f0dfd8' }}>
              <td className="p-2 font-bold">{item.query}</td>
              <td className="p-2">{item.variation}</td>
              <td className="p-2 font-mono">{formatScore(item.expectedStudentScore)}</td>
              <td className="p-2 font-mono">#{item.topCandidate?.studentId ?? '—'} {formatScore(item.topCandidate?.score)}</td>
              <td className="p-2 font-mono">#{item.secondCandidate?.studentId ?? '—'} {formatScore(item.secondCandidate?.score)}</td>
              <td className="p-2 font-mono">{formatScore(item.scoreMargin)}</td>
              <td className="p-2 font-semibold">{item.status}</td>
            </tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  )
}
