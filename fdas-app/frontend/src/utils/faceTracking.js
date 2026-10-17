export const EMPTY_FACE_TRACKER = Object.freeze({ tracks: [], nextId: 1 })

export function faceBoxIou(left, right) {
  if (!left || !right) return 0
  const intersectionLeft = Math.max(left.x, right.x)
  const intersectionTop = Math.max(left.y, right.y)
  const intersectionRight = Math.min(left.x + left.width, right.x + right.width)
  const intersectionBottom = Math.min(left.y + left.height, right.y + right.height)
  const width = Math.max(0, intersectionRight - intersectionLeft)
  const height = Math.max(0, intersectionBottom - intersectionTop)
  const intersection = width * height
  const union = (left.width * left.height) + (right.width * right.height) - intersection
  return union > 0 ? intersection / union : 0
}

export function mirroredFaceBoxX(bbox, sourceWidth, mirrored = true) {
  return mirrored ? sourceWidth - bbox.x - bbox.width : bbox.x
}

export function reconcileFaceTracks(previousState, faces, now = Date.now(), ttlMilliseconds = 4000) {
  const state = previousState || EMPTY_FACE_TRACKER
  const available = (state.tracks || []).filter(track => now - track.lastSeenAt <= ttlMilliseconds)
  const usedTrackIds = new Set()
  let nextId = state.nextId || 1

  const trackedFaces = faces.map(face => {
    const candidates = available
      .filter(track => {
        if (usedTrackIds.has(track.trackId)) return false
        if (face.studentId && track.studentId && face.studentId !== track.studentId) return false
        return true
      })
      .map(track => ({
        track,
        iou: faceBoxIou(track.bbox, face.bbox),
        sameIdentity: Boolean(face.studentId && face.studentId === track.studentId),
      }))
      .filter(candidate => candidate.sameIdentity || candidate.iou >= 0.15)
      .sort((left, right) => (
        Number(right.sameIdentity) - Number(left.sameIdentity)
        || right.iou - left.iou
        || left.track.trackId.localeCompare(right.track.trackId)
      ))

    const matchedTrack = candidates[0]?.track
    const trackId = matchedTrack?.trackId || `face-${nextId++}`
    usedTrackIds.add(trackId)
    return { ...face, trackId }
  })

  return {
    faces: trackedFaces,
    tracker: {
      nextId,
      tracks: trackedFaces.map(face => ({
        trackId: face.trackId,
        bbox: face.bbox,
        studentId: face.studentId || null,
        lastSeenAt: now,
      })),
    },
  }
}
