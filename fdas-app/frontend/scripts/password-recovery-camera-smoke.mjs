import { chromium } from 'playwright'
import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'

if (process.env.FDAS_PASSWORD_RECOVERY_BROWSER_ISOLATED !== '1') {
  throw new Error('Password-recovery browser verification mutates credentials and requires an isolated backend.')
}

const baseUrl = process.env.FDAS_FRONTEND_BASE_URL || 'http://127.0.0.1:5173'
const apiUrl = process.env.FDAS_API_BASE_URL || 'http://127.0.0.1:8000'
const resetToken = process.env.FDAS_BROWSER_EMAIL_RESET_TOKEN
const resetEmail = process.env.FDAS_BROWSER_EMAIL_RESET_EMAIL
const fixturePath = process.env.FDAS_CAMERA_FIXTURE
if (!resetToken || !resetEmail || !fixturePath) throw new Error('Reset-token and camera fixture inputs are required.')

const outputDir = path.resolve('output/playwright/password_recovery_camera')
await mkdir(outputDir, { recursive: true })
const fixtureBase64 = (await readFile(fixturePath)).toString('base64')

const browser = await chromium.launch({ headless: true, args: ['--use-fake-ui-for-media-stream'] })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
await context.addInitScript(({ imageBase64 }) => {
  const originalMediaDevices = navigator.mediaDevices
  if (!originalMediaDevices) return
  Object.defineProperty(originalMediaDevices, 'getUserMedia', {
    configurable: true,
    value: async () => {
      const canvas = document.createElement('canvas')
      canvas.width = 640
      canvas.height = 480
      const drawing = canvas.getContext('2d')
      const image = new Image()
      image.src = `data:image/jpeg;base64,${imageBase64}`
      await image.decode()
      const render = () => {
        drawing.fillStyle = '#1f1713'
        drawing.fillRect(0, 0, canvas.width, canvas.height)
        const scale = Math.min(canvas.width / image.naturalWidth, canvas.height / image.naturalHeight)
        const width = image.naturalWidth * scale
        const height = image.naturalHeight * scale
        drawing.drawImage(image, (canvas.width - width) / 2, (canvas.height - height) / 2, width, height)
      }
      render()
      window.setInterval(render, 100)
      return canvas.captureStream(10)
    },
  })
}, { imageBase64: fixtureBase64 })

const page = await context.newPage()
page.setDefaultTimeout(20000)
const results = []
const pageErrors = []
const nativeDialogs = []
const consoleErrors = []
const expectedConsoleErrors = []
const genericMessage = 'If an eligible account exists for this email, password recovery instructions have been prepared.'
const emailPassword = 'Email-Recovery-456'
const adminCodePassword = 'Admin-Code-789'

page.on('pageerror', error => pageErrors.push(error.message))
page.on('console', message => {
  if (message.type() !== 'error') return
  const value = message.text()
  if (value.includes('400 (Bad Request)')) expectedConsoleErrors.push(value)
  else consoleErrors.push(value)
})
page.on('dialog', async dialog => {
  nativeDialogs.push(`${dialog.type()}: ${dialog.message()}`)
  await dialog.dismiss()
})

async function check(name, callback) {
  try {
    await callback()
    results.push([name, true])
    console.log(`${name}=true`)
  } catch (error) {
    results.push([name, false, error.message])
    console.log(`${name}=false :: ${error.message}`)
  }
}

async function login(email, password, expectedPath = '/admin/dashboard') {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill(email)
  await page.locator('#password').fill(password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(`**${expectedPath}`)
}

async function accessToken() {
  return page.evaluate(() => localStorage.getItem('fdas_access_token'))
}

async function authHeaders() {
  return { Authorization: `Bearer ${await accessToken()}` }
}

async function assertResponsivePage(route) {
  for (const width of [375, 480, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: width <= 480 ? 812 : 1000 })
    await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' })
    const dimensions = await page.locator('main').evaluate(element => ({
      documentWidth: document.documentElement.scrollWidth,
      panelLeft: element.getBoundingClientRect().left,
      panelRight: element.getBoundingClientRect().right,
    }))
    if (dimensions.documentWidth > width || dimensions.panelLeft < 0 || dimensions.panelRight > width) {
      throw new Error(`${route} overflowed at ${width}px`)
    }
  }
}

async function openStudentCamera(student, dialogName) {
  await page.goto(`${baseUrl}/admin/students`, { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Search active students').fill(student.rollNo)
  const row = page.locator('tbody tr').filter({ hasText: student.rollNo })
  await row.getByTitle(dialogName === 'Register Student Face' ? 'Register face' : 'Deep enrollment recovery').click()
  const dialog = page.getByRole('dialog', { name: dialogName })
  await dialog.waitFor()
  await dialog.getByRole('button', { name: /start (face registration|deep recovery)/i }).click()
  await dialog.locator('video').evaluate(video => new Promise((resolve, reject) => {
    if (video.videoWidth > 0) return resolve()
    const timeout = setTimeout(() => reject(new Error('camera video did not become ready')), 8000)
    video.addEventListener('loadedmetadata', () => { clearTimeout(timeout); resolve() }, { once: true })
  }))
  return dialog
}

async function assertPreview(dialog, width) {
  const geometry = await dialog.locator('[data-enrollment-preview]').evaluate(preview => {
    const box = preview.getBoundingClientRect()
    const video = preview.querySelector('video')
    const style = getComputedStyle(video)
    return {
      width: box.width,
      height: box.height,
      ratio: box.width / box.height,
      viewportWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      objectFit: style.objectFit,
      objectPosition: style.objectPosition,
      sourceRatio: video.videoWidth / video.videoHeight,
    }
  })
  if (Math.abs(geometry.ratio - (4 / 3)) > 0.04) throw new Error(`preview is not 4:3 at ${width}px`)
  if (geometry.objectFit !== 'contain' || !geometry.objectPosition.includes('50%')) throw new Error(`video crop protection drifted at ${width}px`)
  if (Math.abs(geometry.sourceRatio - (4 / 3)) > 0.04) throw new Error(`test camera stream is not 4:3 at ${width}px`)
  if (geometry.width > geometry.viewportWidth || geometry.scrollWidth > geometry.viewportWidth) throw new Error(`camera modal overflowed at ${width}px`)
  if (width >= 1024 && (geometry.height < 439 || geometry.height > 521)) throw new Error(`desktop camera height ${geometry.height}px is outside the 440-520px target`)
}

await check('Forgot Password link supports Enter and Space keyboard activation', async () => {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  const link = page.getByRole('link', { name: 'Recover your FDAS password' })
  await link.focus()
  await page.keyboard.press('Enter')
  await page.waitForURL('**/forgot-password')
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('link', { name: 'Recover your FDAS password' }).focus()
  await page.keyboard.press('Space')
  await page.waitForURL('**/forgot-password')
  await page.getByRole('heading', { name: 'Forgot Password' }).waitFor()
})

await check('Forgot Password page returns the same generic result for known and unknown emails', async () => {
  await page.getByLabel('Email address').fill(resetEmail.toUpperCase())
  await page.getByRole('button', { name: 'Send Reset Instructions' }).click()
  const known = await page.getByRole('status').textContent()
  await page.getByLabel('Email address').fill(`unknown.${Date.now()}@example.local`)
  await page.getByRole('button', { name: 'Send Reset Instructions' }).click()
  const unknown = await page.getByRole('status').textContent()
  if (known?.trim() !== genericMessage || unknown?.trim() !== genericMessage || known !== unknown) throw new Error('public recovery response disclosed account state')
  await page.screenshot({ path: path.join(outputDir, '01-forgot-password-generic-response.png') })
})

await check('Recovery auth pages remain responsive from 375 through 1920px', async () => {
  await assertResponsivePage('/forgot-password')
  await assertResponsivePage('/reset-password/admin-code')
  await assertResponsivePage(`/reset-password?token=${encodeURIComponent(resetToken)}`)
})

await check('Email reset validates mismatch and completes without automatic login', async () => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${baseUrl}/reset-password?token=${encodeURIComponent(resetToken)}`, { waitUntil: 'domcontentloaded' })
  await page.locator('#newPassword').fill(emailPassword)
  await page.locator('#confirmPassword').fill('Different-Password-456')
  await page.getByRole('button', { name: 'Reset Password' }).click()
  await page.getByText('New password and confirmation do not match.').waitFor()
  await page.locator('#confirmPassword').fill(emailPassword)
  await page.getByRole('button', { name: 'Reset Password' }).click()
  await page.waitForURL('**/login')
  await page.getByRole('status').filter({ hasText: 'Password reset successfully' }).waitFor()
  if (await accessToken()) throw new Error('password reset automatically authenticated the user')
  const loginResponse = await page.request.post(`${apiUrl}/api/auth/login`, { data: { email: resetEmail, password: emailPassword } })
  if (!loginResponse.ok()) throw new Error('new email-reset password could not authenticate')
  await page.screenshot({ path: path.join(outputDir, '02-email-reset-success.png') })
})

await check('Invalid or expired reset credentials show a safe combined message', async () => {
  await page.goto(`${baseUrl}/reset-password?token=${'x'.repeat(48)}`, { waitUntil: 'domcontentloaded' })
  await page.locator('#newPassword').fill('Invalid-Token-456')
  await page.locator('#confirmPassword').fill('Invalid-Token-456')
  await page.getByRole('button', { name: 'Reset Password' }).click()
  await page.getByRole('alert').filter({ hasText: /invalid, expired, or has already been used/i }).waitFor()
})

let generatedCode = ''
await check('Admin recovery code requires confirmation and is shown once without a final password', async () => {
  await login('admin@fdas.local', 'Admin@12345')
  await page.goto(`${baseUrl}/admin/users`, { waitUntil: 'domcontentloaded' })
  const row = page.locator('tbody tr').filter({ hasText: 'operator.it@fdas.local' })
  await row.getByRole('button', { name: /generate password recovery code/i }).click()
  const confirmation = page.getByRole('dialog', { name: 'Generate Password Recovery Code?' })
  await confirmation.getByText(/verify the operator's identity/i).waitFor()
  await confirmation.getByText(/administrators never see or set it/i).waitFor()
  await page.screenshot({ path: path.join(outputDir, '03-admin-recovery-confirmation.png') })
  await confirmation.getByRole('button', { name: 'Generate Code' }).click()
  const result = page.getByRole('dialog', { name: 'One-Time Recovery Code' })
  generatedCode = await result.locator('#generatedRecoveryCode').inputValue()
  if (!/^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(generatedCode)) throw new Error('generated code format is not copy-friendly Base32 style')
  if ((await result.textContent()).includes(adminCodePassword)) throw new Error('Admin was shown the final password')
  await page.screenshot({ path: path.join(outputDir, '04-admin-recovery-code-shown-once.png') })
  await result.getByRole('button', { name: 'Done' }).click()
  if (await page.getByText(generatedCode).count()) throw new Error('recovery code remained visible after its one-time dialog closed')
})

await check('Operator chooses the final password with the one-time Admin code', async () => {
  await page.evaluate(() => localStorage.removeItem('fdas_access_token'))
  await page.goto(`${baseUrl}/reset-password/admin-code`, { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Registered email').fill('operator.it@fdas.local')
  await page.getByLabel('Recovery code').fill(generatedCode)
  await page.locator('#newPassword').fill(adminCodePassword)
  await page.locator('#confirmPassword').fill(adminCodePassword)
  await page.screenshot({ path: path.join(outputDir, '05-admin-code-reset-form.png') })
  await page.getByRole('button', { name: 'Reset Password' }).click()
  await page.waitForURL('**/login')
  await page.getByRole('status').filter({ hasText: 'Password reset successfully' }).waitFor()
  const loginResponse = await page.request.post(`${apiUrl}/api/auth/login`, { data: { email: 'operator.it@fdas.local', password: adminCodePassword } })
  if (!loginResponse.ok()) throw new Error('new Admin-code password could not authenticate')
})

await check('New password-change notification displays Just now', async () => {
  await login('operator.it@fdas.local', adminCodePassword, '/user/dashboard')
  await page.getByRole('button', { name: /open notifications/i }).click()
  const center = page.getByRole('dialog', { name: 'Notifications' })
  const passwordChanged = center.locator('article').filter({ hasText: 'Account password changed' }).first()
  await passwordChanged.waitFor()
  await passwordChanged.locator('time').filter({ hasText: 'Just now' }).waitFor()
})

// Camera checks below verify rendering geometry. The single-face and deep-detector
// enforcement paths are covered by backend verifiers; stable responses keep the
// visual evidence unobstructed and deterministic here.
await page.route('**/api/face-processing/validate-single-face', route => route.fulfill({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ status: 'SingleFace', message: 'Face detected — ready.', faceCount: 1, ready: true, continuityPassed: true }),
}))
await page.route('**/api/deep-face/validate-recovery-sample', route => route.fulfill({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ success: true, status: 'Ready', message: 'Face detected — deep-ready.', deepFaceCount: 1 }),
}))

await check('Standard enrollment camera is 4:3, uncropped, responsive, and visually documented', async () => {
  await login('admin@fdas.local', 'Admin@12345')
  const headers = await authHeaders()
  const studentResponse = await page.request.get(`${apiUrl}/api/students?status=active`, { headers })
  const students = await studentResponse.json()
  let student = students.find(item => !item.faceRegistered)
  if (!student) {
    const source = students[0]
    const created = await page.request.post(`${apiUrl}/api/students`, {
      headers,
      data: {
        rollNo: `CAM-${Date.now()}`,
        fullName: 'Camera Preview Fixture',
        email: `camera.preview.${Date.now()}@example.local`,
        departmentId: source.departmentId,
        classId: source.classId,
        status: 'Active',
      },
    })
    if (!created.ok()) throw new Error(`unable to create isolated camera fixture: ${await created.text()}`)
    student = await created.json()
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  const dialog = await openStudentCamera(student, 'Register Student Face')
  await dialog.getByText(/^Capturing 1\/25$/).waitFor()
  for (const width of [375, 480, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: width <= 480 ? 812 : 1000 })
    await dialog.locator('.fdas-modal-body').evaluate(element => { element.scrollTop = 0 })
    await assertPreview(dialog, width)
    if (width === 375) await page.screenshot({ path: path.join(outputDir, '07-standard-enrollment-mobile-375.png') })
    if (width === 1440) await page.screenshot({ path: path.join(outputDir, '06-standard-enrollment-desktop-1440.png') })
  }
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await dialog.getByRole('button', { name: /close register student face/i }).click()
})

await check('Deep Enrollment Recovery inherits the same responsive, uncropped camera', async () => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  const headers = await authHeaders()
  const studentResponse = await page.request.get(`${apiUrl}/api/students?status=active`, { headers })
  const students = await studentResponse.json()
  const student = students.find(item => item.studentId === 22 && item.faceRegistered) || students.find(item => item.faceRegistered)
  if (!student) throw new Error('no face-ready student exists in the isolated fixture')
  const dialog = await openStudentCamera(student, 'Deep Enrollment Recovery')
  await dialog.getByText(/^Capturing 1\/8$/).waitFor()
  await dialog.locator('.fdas-modal-body').evaluate(element => { element.scrollTop = 0 })
  await assertPreview(dialog, 1440)
  await page.screenshot({ path: path.join(outputDir, '08-deep-recovery-desktop-1440.png') })
  await page.setViewportSize({ width: 375, height: 812 })
  await dialog.locator('.fdas-modal-body').evaluate(element => { element.scrollTop = 0 })
  await assertPreview(dialog, 375)
  await page.screenshot({ path: path.join(outputDir, '09-deep-recovery-mobile-375.png') })
  await dialog.getByRole('button', { name: 'Cancel' }).click()
})

await browser.close()

console.log(`password_recovery_camera_checks=${results.length}`)
console.log(`password_recovery_camera_failures=${results.filter(([, passed]) => !passed).length}`)
console.log(`page_errors=${pageErrors.length}`)
console.log(`native_dialogs=${nativeDialogs.length}`)
console.log(`console_errors=${consoleErrors.length}`)
console.log(`expected_console_errors=${expectedConsoleErrors.length}`)
for (const value of pageErrors) console.log(`page_error=${JSON.stringify(value)}`)
for (const value of nativeDialogs) console.log(`native_dialog=${JSON.stringify(value)}`)
for (const value of consoleErrors) console.log(`console_error=${JSON.stringify(value)}`)

if (results.some(([, passed]) => !passed) || pageErrors.length || nativeDialogs.length || consoleErrors.length) process.exitCode = 1
