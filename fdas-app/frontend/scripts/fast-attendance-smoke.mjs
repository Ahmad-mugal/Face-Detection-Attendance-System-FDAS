import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

if (process.env.FDAS_FAST_ATTENDANCE_BROWSER_ISOLATED !== '1') {
  throw new Error('Fast-attendance browser smoke requires an isolated backend.')
}

const baseUrl = process.env.FDAS_FRONTEND_BASE_URL || 'http://127.0.0.1:5186'
const outputDir = path.resolve('output/playwright/fast-attendance')
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true, args: ['--use-fake-ui-for-media-stream'] })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
await context.addInitScript(() => {
  Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
    configurable: true,
    value: async () => {
      const canvas = document.createElement('canvas')
      canvas.width = 640
      canvas.height = 480
      const drawing = canvas.getContext('2d')
      drawing.fillStyle = '#33251f'
      drawing.fillRect(0, 0, canvas.width, canvas.height)
      drawing.fillStyle = '#d4a017'
      drawing.fillRect(40, 60, 120, 150)
      drawing.fillStyle = '#c4533a'
      drawing.fillRect(240, 80, 130, 160)
      drawing.fillStyle = '#887369'
      drawing.fillRect(470, 70, 100, 140)
      return canvas.captureStream(10)
    },
  })
})

const page = await context.newPage()
page.setDefaultTimeout(20000)
const failures = []
const pageErrors = []
const consoleErrors = []
let fastRequests = 0
let csDepartmentValue = ''

page.on('pageerror', error => pageErrors.push(error.message))
page.on('console', message => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})

const face = (faceId, faceIndex, bbox, status, identity = {}) => ({
  faceId,
  faceIndex,
  bbox: {
    ...bbox,
    normalizedX: bbox.x / 640,
    normalizedY: bbox.y / 480,
    normalizedWidth: bbox.width / 640,
    normalizedHeight: bbox.height / 480,
  },
  detectionScore: 0.99,
  status,
  message: status,
  quality: { passed: true },
  attendanceMarked: status === 'AttendanceMarked',
  attendanceRecordId: status === 'AttendanceMarked' ? 9000 + faceIndex : null,
  recognitionConfidence: identity.studentId ? 0.94 : null,
  secondRecognitionConfidence: identity.studentId ? 0.42 : null,
  identityMargin: identity.studentId ? 0.52 : null,
  thresholdUsed: 0.85,
  requiredMargin: 0.07,
  recognitionProvider: 'InsightFace',
  recognitionEncodingVersion: 'arcface_v1',
  recognitionMethod: 'mean_top_3',
  livenessStatus: 'NotChecked',
  ...identity,
})

await page.route('**/api/attendance/mark-by-face-fast', async route => {
  fastRequests += 1
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      attendanceMode: 'FAST_MULTI_FACE',
      sessionId: 1,
      departmentId: 1,
      departmentName: 'Computer Science',
      sourceWidth: 640,
      sourceHeight: 480,
      rotationDegrees: 0,
      mirroredPreview: true,
      faces: [
        face('face-1', 1, { x: 110, y: 85, width: 105, height: 145 }, 'AttendanceMarked', {
          studentId: 22,
          studentName: 'Student Twenty Two',
          rollNo: 'CS-022',
        }),
        face('face-2', 2, { x: 265, y: 95, width: 110, height: 150 }, 'AlreadyMarked', {
          studentId: 24,
          studentName: 'Student Twenty Four',
          rollNo: 'CS-024',
        }),
        face('face-3', 3, { x: 430, y: 90, width: 90, height: 140 }, 'Unknown'),
      ],
      facesDetected: 3,
      markedCount: 1,
      alreadyMarkedCount: 1,
      rejectedCount: 1,
      candidateStudentCount: 4,
      candidateEmbeddingCount: 85,
      galleryCacheHit: true,
      timing: {
        decodeMilliseconds: 4,
        detectorMilliseconds: 230,
        alignmentMilliseconds: 2,
        embeddingMilliseconds: 650,
        galleryMilliseconds: 10,
        matchingMilliseconds: 1,
        recognitionMilliseconds: 897,
        serviceMilliseconds: 920,
        databaseMilliseconds: 45,
        totalMilliseconds: 965,
      },
      diagnostics: {},
    }),
  })
})

async function check(name, callback) {
  try {
    await callback()
    console.log(`${name}=true`)
  } catch (error) {
    failures.push(`${name}: ${error.message}`)
    console.log(`${name}=false :: ${error.message}`)
  }
}

async function assertOverlayFits(width, zoom = 1) {
  await page.setViewportSize({ width, height: width <= 480 ? 812 : 1000 })
  await page.evaluate(value => { document.body.style.zoom = String(value) }, zoom)
  await page.waitForTimeout(100)
  const geometry = await page.locator('[data-face-overlay]').evaluate(svg => {
    const camera = svg.parentElement.getBoundingClientRect()
    const boxes = [...svg.querySelectorAll('[data-face-box]')].map(box => {
      const rect = box.getBoundingClientRect()
      return {
        id: box.getAttribute('data-face-box'),
        status: box.getAttribute('data-face-status'),
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
      }
    })
    return {
      camera: { left: camera.left, right: camera.right, top: camera.top, bottom: camera.bottom },
      boxes,
      scrollWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
      preserveAspectRatio: svg.getAttribute('preserveAspectRatio'),
      videoObjectFit: getComputedStyle(svg.parentElement.querySelector('video')).objectFit,
    }
  })
  if (geometry.boxes.length !== 3) throw new Error(`expected 3 boxes, received ${geometry.boxes.length}`)
  if (geometry.preserveAspectRatio !== 'xMidYMid meet' || geometry.videoObjectFit !== 'contain') {
    throw new Error(`video/overlay fit mismatch at ${width}px / zoom ${zoom}`)
  }
  if (geometry.scrollWidth > geometry.viewportWidth + 1) throw new Error(`page overflowed at ${width}px / zoom ${zoom}`)
  for (const box of geometry.boxes) {
    if (
      box.left < geometry.camera.left - 2
      || box.right > geometry.camera.right + 2
      || box.top < geometry.camera.top - 2
      || box.bottom > geometry.camera.bottom + 2
    ) throw new Error(`${box.id} escaped the camera at ${width}px / zoom ${zoom}`)
  }
  if (!(geometry.boxes[0].left > geometry.boxes[1].left && geometry.boxes[1].left > geometry.boxes[2].left)) {
    throw new Error(`mirrored box order was incorrect at ${width}px / zoom ${zoom}`)
  }
}

await check('admin can enter fast attendance screen', async () => {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill('admin@fdas.local')
  await page.locator('#password').fill('Admin@12345')
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL('**/admin/dashboard')
  await page.goto(`${baseUrl}/admin/attendance/live`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /Start Camera/i }).waitFor()
  if (await page.getByText(/Fast Mode: liveness is disabled/i).count()) throw new Error('Fast Mode warning banner should not be displayed')
  if (await page.getByText(/Liveness challenge:/i).count()) throw new Error('secure liveness prompt leaked into stopped fast mode')
})

await check('fast scan displays all independent face outcomes without liveness', async () => {
  const department = page.locator('select').first()
  await department.selectOption({ label: 'Computer Science' })
  csDepartmentValue = await department.inputValue()
  await page.waitForTimeout(500)
  const startSession = page.getByRole('button', { name: /start session/i })
  if (await startSession.isEnabled()) await startSession.click()
  await page.getByText(/active session #\d+ loaded|attendance session #\d+ started/i).waitFor()
  await page.getByRole('button', { name: 'Start Camera', exact: true }).click()
  await page.getByText('Camera Active', { exact: true }).waitFor()
  await page.getByRole('button', { name: 'Start Scanning', exact: true }).click()
  await page.getByText('Faces detected: 3', { exact: true }).waitFor()
  await page.locator('[data-face-overlay]').waitFor()
  await page.locator('[data-face-overlay] text').filter({ hasText: /Student Twenty Two.*Marked/i }).waitFor()
  await page.locator('[data-face-overlay] text').filter({ hasText: /Student Twenty Four.*Already marked/i }).waitFor()
  await page.locator('[data-face-overlay] text').filter({ hasText: /^Unrecognized$/i }).waitFor()
  if (await page.getByText(/Liveness challenge:/i).count()) throw new Error('liveness challenge ran in fast mode')
  await page.getByRole('button', { name: 'Stop Scanning', exact: true }).click()
  if (fastRequests < 1) throw new Error('fast endpoint was not called')
})

await check('boxes remain aligned and contained at required widths and zoom states', async () => {
  await page.getByRole('button', { name: 'Start Scanning', exact: true }).click()
  await page.locator('[data-face-overlay]').waitFor()
  for (const width of [375, 480, 768, 1024, 1440, 1920]) await assertOverlayFits(width)
  await assertOverlayFits(1024, 0.8)
  await assertOverlayFits(1024, 1.25)
  await page.evaluate(() => { document.body.style.zoom = '1' })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.screenshot({ path: path.join(outputDir, 'fast-multi-face-overlay.png'), fullPage: true })
})

await check('department change stops camera, scanning, and stale overlays', async () => {
  const department = page.locator('select').first()
  const alternateValue = await department.locator('option').evaluateAll((options, current) => (
    options.find(option => option.value && option.value !== current)?.value || ''
  ), csDepartmentValue)
  if (!alternateValue) throw new Error('no alternate department was available')
  await department.selectOption(alternateValue)
  await page.getByText('Camera stopped', { exact: true }).waitFor()
  if (await page.locator('[data-face-overlay]').count()) throw new Error('stale face overlay survived department change')
  if (await page.getByRole('button', { name: 'Stop Scanning', exact: true }).count()) throw new Error('scan remained active after department change')
})

await check('camera denial is handled without enabling scanning', async () => {
  await page.locator('select').first().selectOption(csDepartmentValue)
  await page.getByText(/active session #\d+ loaded|attendance session #\d+ started/i).waitFor()
  await page.evaluate(() => {
    Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
      configurable: true,
      value: async () => { throw new DOMException('denied', 'NotAllowedError') },
    })
  })
  await page.getByRole('button', { name: 'Start Camera', exact: true }).click()
  await page.getByText(/Camera permission was denied/i).waitFor()
  if (await page.getByRole('button', { name: 'Start Scanning', exact: true }).isEnabled()) {
    throw new Error('scanning became enabled after camera denial')
  }
})

await browser.close()

console.log(`page_errors=${pageErrors.length}`)
console.log(`console_errors=${consoleErrors.length}`)
if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(' | ')}`)
if (consoleErrors.length) failures.push(`console errors: ${consoleErrors.join(' | ')}`)
if (failures.length) throw new Error(failures.join('\n'))
console.log('fast_attendance_browser_smoke_passed=true')
