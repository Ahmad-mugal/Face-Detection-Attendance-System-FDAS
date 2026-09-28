import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const baseUrl = process.env.FDAS_FRONTEND_BASE_URL || 'http://127.0.0.1:5173'
if (process.env.FDAS_SMOKE_ISOLATED !== '1') {
  throw new Error('phase5-smoke performs registration checks and must run only with FDAS_SMOKE_ISOLATED=1.')
}
const outputDir = path.resolve('output/playwright')
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({
  headless: true,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
})
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(8000)
const consoleErrors = []
const pageErrors = []
const nativeDialogs = []
const results = []
const unavailableMessage = 'Unable to connect to the FDAS server. Please make sure the backend is running.'
const browserRegistrationEmail = `phase10.4.browser.${Date.now()}@fdas.local`
const browserProfileName = `FDAS Phase 10.11 Administrator ${Date.now()}`

page.on('console', message => {
  if (message.type() === 'error') {
    consoleErrors.push({
      text: message.text(),
      location: message.location(),
    })
  }
})

page.on('pageerror', error => {
  pageErrors.push(error.message)
})

page.on('dialog', async dialog => {
  if (dialog.type() === 'beforeunload') await dialog.accept()
  else {
    nativeDialogs.push({ type: dialog.type(), message: dialog.message() })
    await dialog.dismiss()
  }
})

async function check(name, fn) {
  try {
    await fn()
    results.push([name, true])
    console.log(`${name}=true`)
  } catch (error) {
    results.push([name, false, error.message])
    console.log(`${name}=false :: ${error.message}`)
  }
}

async function login(email, password, expectedPath) {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill(email)
  await page.locator('#password').fill(password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(`**${expectedPath}`, { timeout: 10000 })
}

async function fillRegistration({ fullName, email, password }) {
  await page.getByLabel('Full Name').fill(fullName)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByLabel('Requested Department').selectOption({ index: 1 })
}

await check('/login loads', async () => {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /(admin|system) access/i }).waitFor()
  await page.screenshot({ path: path.join(outputDir, '01-login.png'), fullPage: true })
})

await check('/register loads', async () => {
  await page.goto(`${baseUrl}/register`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /request an account/i }).waitFor()
  await page.getByLabel('Requested Department').locator('option').nth(1).waitFor({ state: 'attached' })
  await page.screenshot({ path: path.join(outputDir, '02-register.png'), fullPage: true })
})

await check('empty registration fields show validation', async () => {
  await page.getByRole('button', { name: /submit registration request/i }).click()
  await page.getByText('Full name is required.').waitFor()
  await page.getByText('Email is required.').waitFor()
  await page.getByText('Password is required.').waitFor()
  await page.getByText('Please select a department.').waitFor()
})

await check('malformed email and short password show validation', async () => {
  await fillRegistration({ fullName: 'Browser Validation User', email: 'not-an-email', password: 'Short1@' })
  await page.getByRole('button', { name: /submit registration request/i }).click()
  await page.getByText('Enter a valid email address.').waitFor()
  await page.getByText('Password must be at least 8 characters long.').waitFor()
})

await check('valid .local registration works', async () => {
  await page.getByLabel('Email').fill(`  ${browserRegistrationEmail.toUpperCase()}  `)
  await page.getByLabel('Password').fill('Browser@12345')
  await page.getByRole('button', { name: /submit registration request/i }).click()
  await page.getByText(/registration request submitted/i).waitFor({ timeout: 10000 })
})

await check('duplicate registration shows clean conflict', async () => {
  await fillRegistration({ fullName: 'Duplicate Browser User', email: browserRegistrationEmail.toUpperCase(), password: 'Browser@12345' })
  await page.getByRole('button', { name: /submit registration request/i }).click()
  await page.getByText('An account with this email already exists.').waitFor({ timeout: 10000 })
})

await check('registration backend unavailable shows friendly error', async () => {
  await fillRegistration({ fullName: 'Unavailable Browser User', email: 'phase10.4.unavailable@fdas.local', password: 'Browser@12345' })
  await page.route('**/api/auth/register-request', route => route.abort('connectionrefused'))
  await page.getByRole('button', { name: /submit registration request/i }).click()
  await page.getByText(unavailableMessage).waitFor({ timeout: 10000 })
  await page.unroute('**/api/auth/register-request')
})

await check('login backend unavailable shows friendly error', async () => {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.route('**/api/auth/login', route => route.abort('connectionrefused'))
  await page.getByLabel('Email').fill('admin@fdas.local')
  await page.locator('#password').fill('Admin@12345')
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.getByText(unavailableMessage).waitFor({ timeout: 10000 })
  await page.unroute('**/api/auth/login')
})

await check('wrong login shows error', async () => {
  await page.getByLabel('Email').fill('admin@fdas.local')
  await page.locator('#password').fill('WrongPassword')
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.getByText(/invalid email or password/i).waitFor({ timeout: 10000 })
})

await check('admin login works', async () => {
  await login('admin@fdas.local', 'Admin@12345', '/admin/dashboard')
})

await check('admin dashboard opens', async () => {
  await page.getByRole('heading', { name: /fdas dashboard/i }).waitFor()
  await page.screenshot({ path: path.join(outputDir, '03-admin-dashboard.png'), fullPage: true })
})

await check('approval UI distinguishes email delivery success and failure', async () => {
  await page.goto(`${baseUrl}/admin/requests`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /pending user requests/i }).waitFor()
  const requestRow = page.getByRole('row').filter({ hasText: browserRegistrationEmail })
  await requestRow.waitFor()
  let emailSent = false
  await page.route('**/api/admin/users/*/approve', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      user: {},
      emailNotificationSent: emailSent,
      emailNotificationMessage: emailSent
        ? 'Approval email sent successfully.'
        : 'Approval email could not be sent.',
    }),
  }))

  await requestRow.getByRole('button', { name: /^approve$/i }).click()
  await page.getByRole('dialog', { name: /approve user request/i }).getByRole('button', { name: 'Approve User', exact: true }).click()
  await page.getByText('Operator approved, but the notification email could not be sent.').waitFor()
  await page.getByRole('button', { name: /dismiss notification/i }).click()

  emailSent = true
  await requestRow.getByRole('button', { name: /^approve$/i }).click()
  await page.getByRole('dialog', { name: /approve user request/i }).getByRole('button', { name: 'Approve User', exact: true }).click()
  await page.getByText('Operator approved. Approval email sent successfully.').waitFor()
  await page.unroute('**/api/admin/users/*/approve')
})

await check('approved operator resend uses custom dialog and safe feedback', async () => {
  await page.goto(`${baseUrl}/admin/users`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /manage users/i }).waitFor()
  const operatorRow = page.getByRole('row').filter({ hasText: 'operator.cs@fdas.local' })
  await operatorRow.waitFor()
  await page.route('**/api/admin/users/*/resend-approval-email', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      user: {},
      emailNotificationSent: false,
      emailNotificationMessage: 'Approval email unavailable because SMTP is not configured.',
    }),
  }))
  await operatorRow.getByRole('button', { name: /resend approval email/i }).click()
  const resendDialog = page.getByRole('dialog', { name: /resend approval email/i })
  await resendDialog.waitFor()
  await resendDialog.getByRole('button', { name: /send email/i }).click()
  await page.getByText('Approval email unavailable because SMTP is not configured.').waitFor()
  await page.unroute('**/api/admin/users/*/resend-approval-email')
})

await check('live attendance log opens reports', async () => {
  await page.goto(`${baseUrl}/admin/dashboard`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /fdas dashboard/i }).waitFor()
  await page.getByRole('link', { name: /open reports/i }).click()
  await page.waitForURL('**/admin/analytics', { timeout: 10000 })
  await page.getByRole('heading', { name: /attendance reports/i }).waitFor()
  await page.goto(`${baseUrl}/admin/dashboard`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /fdas dashboard/i }).waitFor()
  await page.waitForTimeout(600)
  await page.screenshot({ path: path.join(outputDir, 'phase10_11-dashboard-analytics-cta.png'), fullPage: true })
})

await check('profile menu and profile route work', async () => {
  await page.getByRole('button', { name: /open profile menu/i }).click()
  await page.getByRole('menuitem', { name: /view profile/i }).click()
  await page.waitForURL('**/account/profile', { timeout: 10000 })
  await page.getByRole('heading', { name: /account profile/i }).waitFor()
  await page.getByText(/account information/i).waitFor()
  await page.waitForTimeout(600)
  await page.screenshot({ path: path.join(outputDir, 'phase10_11-account-profile.png'), fullPage: true })
})

await check('profile update and password validation are functional', async () => {
  await page.getByLabel('Full name').fill(browserProfileName)
  await page.getByRole('button', { name: /save changes/i }).click()
  await page.getByText('Profile updated successfully.').waitFor({ timeout: 10000 })
  await page.getByLabel('Current password').fill('IncorrectPassword@123')
  await page.getByLabel('New password', { exact: true }).fill('NewPassword@123')
  await page.getByLabel('Confirm new password', { exact: true }).fill('NewPassword@123')
  await page.getByRole('button', { name: /change password/i }).click()
  await page.getByText('Current password is incorrect.').waitFor({ timeout: 10000 })
  await page.getByLabel('Current password').fill('Admin@12345')
  await page.getByLabel('New password', { exact: true }).fill('Phase10.11@123')
  await page.getByLabel('Confirm new password', { exact: true }).fill('Phase10.11@123')
  await page.getByRole('button', { name: /change password/i }).click()
  await page.getByText('Password changed successfully.').waitFor({ timeout: 10000 })
})

await check('account preferences route and persistence work', async () => {
  await page.getByRole('button', { name: /open profile menu/i }).click()
  await page.getByRole('menuitem', { name: /account preferences/i }).click()
  await page.waitForURL('**/account/preferences', { timeout: 10000 })
  await page.getByRole('heading', { name: /account preferences/i }).waitFor()
  await page.getByRole('radio', { name: /compact/i }).check()
  await page.getByRole('checkbox', { name: /reduce interface motion/i }).check()
  await page.reload({ waitUntil: 'domcontentloaded' })
  if (!(await page.getByRole('radio', { name: /compact/i }).isChecked())) throw new Error('Table density did not persist.')
  if (!(await page.getByRole('checkbox', { name: /reduce interface motion/i }).isChecked())) throw new Error('Reduced motion did not persist.')
  await page.screenshot({ path: path.join(outputDir, 'phase10_11-account-preferences.png'), fullPage: true })
})

await check('admin dashboard backend unavailable shows friendly error', async () => {
  await page.goto(`${baseUrl}/admin/dashboard`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /fdas dashboard/i }).waitFor()
  await page.route('**/api/dashboard/summary', route => route.abort('connectionrefused'))
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.getByText(unavailableMessage).waitFor({ timeout: 10000 })
  await page.unroute('**/api/dashboard/summary')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /fdas dashboard/i }).waitFor()
})

await check('admin users page opens', async () => {
  await page.goto(`${baseUrl}/admin/users`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /manage users/i }).waitFor()
})

await check('admin classes page opens', async () => {
  await page.goto(`${baseUrl}/admin/classes`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /manage classes/i }).waitFor()
})

await check('admin students page opens', async () => {
  await page.goto(`${baseUrl}/admin/students`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /active students/i, level: 1 }).waitFor()
})

await check('student edit dialog is accessible and fully dismissible', async () => {
  const editButton = page.getByTitle('Edit student').first()
  await editButton.click()
  const dialog = page.getByRole('dialog', { name: /edit student/i })
  await dialog.waitFor()
  if (await page.evaluate(() => document.body.style.overflow) !== 'hidden') throw new Error('Body scroll was not locked while dialog was open.')
  await page.screenshot({ path: path.join(outputDir, 'phase10_11-student-edit-dialog.png') })
  await dialog.getByRole('button', { name: /cancel/i }).click()
  await dialog.waitFor({ state: 'detached' })
  if (await page.evaluate(() => document.body.style.overflow) === 'hidden') throw new Error('Body scroll remained locked after Cancel.')
  await editButton.click()
  await page.keyboard.press('Escape')
  await dialog.waitFor({ state: 'detached' })
  if (await page.locator('.fdas-modal-backdrop').count()) throw new Error('Backdrop remained after Escape.')
})

await check('student destructive action uses custom dialog', async () => {
  await page.getByRole('button', { name: /deactivate|reactivate/i }).first().click()
  const dialog = page.getByRole('dialog', { name: /deactivate student|reactivate student/i })
  await dialog.waitFor()
  await page.screenshot({ path: path.join(outputDir, 'phase10_11-student-status-dialog.png') })
  await dialog.getByRole('button', { name: /cancel/i }).click()
  await dialog.waitFor({ state: 'detached' })
})

await check('dialog and profile remain responsive at mobile width', async () => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.getByTitle('Edit student').first().click()
  const dialog = page.getByRole('dialog', { name: /edit student/i })
  await dialog.waitFor()
  const box = await dialog.boundingBox()
  if (!box || box.x < 0 || box.x + box.width > 375) throw new Error('Dialog overflowed the mobile viewport.')
  await page.screenshot({ path: path.join(outputDir, 'phase10_11-mobile-dialog.png') })
  await page.keyboard.press('Escape')
  await page.goto(`${baseUrl}/account/profile`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /account profile/i }).waitFor()
  if ((await page.evaluate(() => document.documentElement.scrollWidth)) > 375) throw new Error('Profile page has horizontal overflow at 375px.')
  await page.screenshot({ path: path.join(outputDir, 'phase10_11-mobile-profile.png'), fullPage: true })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${baseUrl}/admin/students`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /active students/i, level: 1 }).waitFor()
})

await check('deep enrollment recovery is available for existing students', async () => {
  await page.getByRole('button', { name: /deep enrollment recovery for/i }).first().click()
  await page.getByRole('heading', { name: /deep enrollment recovery/i, level: 2 }).waitFor()
  await page.getByText(/current deep embeddings/i).waitFor({ timeout: 10000 })
  await page.getByText(/every counted sample must also pass the local deep detector/i).waitFor()
  await page.getByRole('button', { name: /close deep enrollment recovery/i }).click()
})

await check('admin add student page opens', async () => {
  await page.goto(`${baseUrl}/admin/students/add`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /add new student/i }).waitFor()
  await page.getByText(/capture starts or resumes after one face remains stable/i).waitFor()
})

await check('production attendance page is clean and camera controls work', async () => {
  await page.goto(`${baseUrl}/admin/attendance/live`, { waitUntil: 'domcontentloaded' })
  const departmentSelect = page.locator('select').first()
  await departmentSelect.selectOption({ label: 'Computer Science' })
  await page.waitForTimeout(500)
  if (await page.getByRole('button', { name: /start session/i }).isEnabled()) {
    await page.getByRole('button', { name: /start session/i }).click()
  }
  await page.getByText(/active session #\d+ loaded|attendance session #\d+ started/i).waitFor({ timeout: 15000 })
  await page.getByRole('button', { name: 'Start Scanning', exact: true }).waitFor()
  if (await page.getByText(/live attendance & liveness operational rules/i).count()) throw new Error('Operational Rules remained visible.')
  if (await page.getByText(/identity integrity diagnostic/i).count()) throw new Error('Identity diagnostic remained visible.')
  if (await page.getByRole('button', { name: /capture diagnostic/i }).count()) throw new Error('Diagnostic capture action remained visible.')
  if (await page.getByText(/phase 10\.9b controlled policy enabled/i).count()) {
    throw new Error('Controlled Phase 10.9B policy remained visible after final activation.')
  }
  if (await page.getByRole('button', { name: /start controlled #22/i }).count()) {
    throw new Error('Controlled Student #22 action remained visible after final activation.')
  }
  await page.getByRole('button', { name: 'Start Camera', exact: true }).click()
  await page.getByText('Camera Active', { exact: true }).waitFor({ timeout: 10000 })
  await page.getByRole('button', { name: 'Stop Camera', exact: true }).click()
  await page.getByText('Camera stopped', { exact: true }).waitFor()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(outputDir, 'phase10_11-live-attendance.png'), fullPage: true })
})

await check('production pages fit all required responsive widths', async () => {
  const widths = [375, 480, 768, 1024, 1280, 1440, 1920]
  const routes = [
    ['/admin/attendance/live', /attendance marking/i],
    ['/account/profile', /account profile/i],
    ['/account/preferences', /account preferences/i],
  ]
  for (const width of widths) {
    await page.setViewportSize({ width, height: width <= 480 ? 812 : 1000 })
    for (const [route, heading] of routes) {
      await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' })
      await page.getByRole('heading', { name: heading }).waitFor()
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
      if (overflow > 1) throw new Error(`${route} overflowed by ${overflow}px at ${width}px.`)
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
})

if (process.env.FDAS_PHASE10_9_CONTROLLED_UI === '1') {
  await check('phase10.9 no session keeps controlled action unavailable', async () => {
    await page.route('**/api/attendance-sessions/active**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '[]',
    }))
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: /attendance marking/i }).waitFor()
    await page.getByRole('button', { name: /attendance paused/i }).waitFor()
    if (await page.getByRole('button', { name: 'Start Controlled #22 Phase 10.9B Test', exact: true }).count()) {
      throw new Error('Controlled action was visible without an active session and camera.')
    }
    await page.unroute('**/api/attendance-sessions/active**')
  })

  await check('phase10.9 active CS admin camera shows only controlled #22 action', async () => {
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.locator('select').first().selectOption({ label: 'Computer Science' })
    await page.getByText(/active session #\d+ loaded/i).waitFor({ timeout: 15000 })
    await page.getByText(/phase 10\.9b controlled policy enabled/i).waitFor({ timeout: 15000 })
    await page.getByText(/22 valid embeddings/i).waitFor()
    await page.getByRole('button', { name: 'Start Camera', exact: true }).click()
    await page.getByText(/phase 10\.9b controlled policy enabled/i).waitFor()
    await page.getByText(/controlled threshold 0\.800000 and margin 0\.100000 apply only here; production remains 0\.850000 \/ 0\.070000/i).waitFor()
    await page.getByRole('button', { name: 'Start Controlled #22 Phase 10.9B Test', exact: true }).waitFor()
    if (await page.getByRole('button', { name: 'Start Scanning', exact: true }).count()) {
      throw new Error('General attendance action became available during the controlled test.')
    }
    await page.getByText(/identity integrity diagnostic/i).waitFor()
  })
}

await check('admin timing page opens', async () => {
  await page.goto(`${baseUrl}/admin/timing`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /attendance timing/i }).waitFor()
})

await check('logout works', async () => {
  await page.getByRole('button', { name: /open profile menu/i }).click()
  await page.getByRole('menuitem', { name: /^logout$/i }).click()
  const leaveDialog = page.getByRole('dialog', { name: /leave live attendance/i })
  if (await leaveDialog.count()) await leaveDialog.getByRole('button', { name: /leave page/i }).click()
  await page.waitForURL('**/login', { timeout: 10000 })
})

await check('operator login works', async () => {
  await login('operator.cs@fdas.local', 'Operator@12345', '/user/dashboard')
})

await check('operator dashboard opens', async () => {
  await page.getByRole('heading', { name: /department dashboard/i }).waitFor()
  await page.screenshot({ path: path.join(outputDir, '04-operator-dashboard.png'), fullPage: true })
})

await check('operator sees final normal attendance without development diagnostics', async () => {
  await page.goto(`${baseUrl}/user/attendance`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /attendance marking/i }).waitFor()
  await page.getByRole('button', { name: 'Start Scanning', exact: true }).waitFor()
  if (await page.getByText(/identity integrity diagnostic/i).count()) {
    throw new Error('Admin-only identity diagnostic was visible to an ordinary operator.')
  }
  if (await page.getByText(/admin policy/i).count()) {
    throw new Error('Admin-only threshold details were visible to an ordinary operator.')
  }
  if (await page.getByRole('button', { name: /start controlled #22/i }).count()) {
    throw new Error('Controlled Student #22 action was visible to an ordinary operator.')
  }
  await page.goto(`${baseUrl}/user/dashboard`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /department dashboard/i }).waitFor()
})

await check('operator dashboard backend unavailable shows friendly error', async () => {
  await page.route('**/api/dashboard/summary', route => route.abort('connectionrefused'))
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.getByText(unavailableMessage).waitFor({ timeout: 10000 })
  await page.unroute('**/api/dashboard/summary')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /department dashboard/i }).waitFor()
})

await check('operator cannot access /admin/users', async () => {
  await page.goto(`${baseUrl}/admin/users`, { waitUntil: 'domcontentloaded' })
  await page.waitForURL('**/user/dashboard', { timeout: 10000 })
})

await browser.close()

console.log(`console_errors=${consoleErrors.length}`)
for (const error of consoleErrors) {
  console.log(`console_error=${JSON.stringify(error)}`)
}
console.log(`page_errors=${pageErrors.length}`)
for (const error of pageErrors) {
  console.log(`page_error=${JSON.stringify(error)}`)
}

console.log(`native_dialogs=${nativeDialogs.length}`)
for (const dialog of nativeDialogs) console.log(`native_dialog=${JSON.stringify(dialog)}`)

if (results.some(([, passed]) => !passed) || pageErrors.length > 0 || nativeDialogs.length > 0) {
  process.exitCode = 1
}
