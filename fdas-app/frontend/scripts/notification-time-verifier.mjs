import assert from 'node:assert/strict'
import { notificationRelativeTime, parseBackendUtc } from '../src/utils/notificationTime.js'

const now = new Date('2026-09-28T00:00:00Z')
const checks = [
  ['newly created notification', notificationRelativeTime('2026-09-27T23:59:30', now), 'Just now'],
  ['one minute old', notificationRelativeTime('2026-09-27T23:59:00', now), '1m ago'],
  ['five minutes old', notificationRelativeTime('2026-09-27T23:55:00', now), '5m ago'],
  ['one hour old', notificationRelativeTime('2026-09-27T23:00:00', now), '1h ago'],
]

for (const [name, actual, expected] of checks) {
  assert.equal(actual, expected, name)
  console.log(`${name}=true (${actual})`)
}

const expectedEpoch = Date.parse('2026-09-28T00:00:00Z')
const timestampChecks = [
  ['timezone-less UTC API timestamp', '2026-09-28T00:00:00'],
  ['explicit Z timestamp', '2026-09-28T00:00:00Z'],
  ['explicit timezone-offset timestamp', '2026-09-28T05:00:00+05:00'],
]

for (const [name, value] of timestampChecks) {
  assert.equal(parseBackendUtc(value)?.getTime(), expectedEpoch, name)
  console.log(`${name}=true`)
}

console.log(`notification_time_checks=${checks.length + timestampChecks.length}`)
