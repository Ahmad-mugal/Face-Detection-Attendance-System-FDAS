import assert from 'node:assert/strict'
import {
  EMPTY_FACE_TRACKER,
  faceBoxIou,
  mirroredFaceBoxX,
  reconcileFaceTracks,
} from '../src/utils/faceTracking.js'

const first = reconcileFaceTracks(EMPTY_FACE_TRACKER, [
  { faceId: 'face-1', bbox: { x: 10, y: 20, width: 100, height: 120 }, studentId: 22 },
  { faceId: 'face-2', bbox: { x: 300, y: 30, width: 90, height: 110 }, studentId: 24 },
], 1000)
assert.deepEqual(first.faces.map(face => face.trackId), ['face-1', 'face-2'])

const moved = reconcileFaceTracks(first.tracker, [
  { faceId: 'server-1', bbox: { x: 305, y: 32, width: 90, height: 110 }, studentId: 24 },
  { faceId: 'server-2', bbox: { x: 16, y: 24, width: 100, height: 120 }, studentId: 22 },
], 1500)
assert.deepEqual(moved.faces.map(face => face.trackId), ['face-2', 'face-1'])
assert.ok(faceBoxIou(first.faces[0].bbox, moved.faces[1].bbox) > 0.8)

const crossedIdentity = reconcileFaceTracks(moved.tracker, [
  { faceId: 'server-3', bbox: { x: 300, y: 30, width: 90, height: 110 }, studentId: 22 },
  { faceId: 'server-4', bbox: { x: 10, y: 20, width: 100, height: 120 }, studentId: 24 },
], 2000)
assert.deepEqual(crossedIdentity.faces.map(face => face.trackId), ['face-1', 'face-2'])

const expired = reconcileFaceTracks(crossedIdentity.tracker, [
  { faceId: 'server-5', bbox: { x: 300, y: 30, width: 90, height: 110 } },
], 7001)
assert.equal(expired.faces[0].trackId, 'face-3')

const overlapping = reconcileFaceTracks(EMPTY_FACE_TRACKER, [
  { faceId: 'overlap-1', bbox: { x: 100, y: 100, width: 120, height: 140 } },
  { faceId: 'overlap-2', bbox: { x: 150, y: 110, width: 120, height: 140 } },
], 8000)
const overlappingMoved = reconcileFaceTracks(overlapping.tracker, [
  { faceId: 'overlap-3', bbox: { x: 105, y: 102, width: 120, height: 140 } },
  { faceId: 'overlap-4', bbox: { x: 155, y: 112, width: 120, height: 140 } },
], 8200)
assert.equal(new Set(overlappingMoved.faces.map(face => face.trackId)).size, 2)
assert.deepEqual(overlappingMoved.faces.map(face => face.trackId), overlapping.faces.map(face => face.trackId))

assert.equal(mirroredFaceBoxX({ x: 10, width: 100 }, 640, true), 530)
assert.equal(mirroredFaceBoxX({ x: 10, width: 100 }, 640, false), 10)
assert.equal(faceBoxIou({ x: 0, y: 0, width: 10, height: 10 }, { x: 20, y: 20, width: 10, height: 10 }), 0)

console.log('fast_attendance_frontend_unit=PASS')
