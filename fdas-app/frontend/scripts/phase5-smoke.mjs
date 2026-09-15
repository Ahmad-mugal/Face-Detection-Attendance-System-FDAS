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
const results = []
const unavailableMessage = 'Unable to connect to the FDAS server. Please make sure the backend is running.'
const browserRegistrationEmail = `phase10.4.browser.${Date.now()}@fdas.local`

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

await check('admin dashboard backend unavailable shows friendly error', async () => {
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
  await page.getByRole('heading', { name: /all students/i }).waitFor()
})

await check('deep enrollment recovery is available for existing students', async () => {
  await page.getByRole('button', { name: /deep enrollment recovery for/i }).first().click()
  await page.getByRole('heading', { name: /deep enrollment recovery/i, level: 2 }).waitFor()
  await page.getByText(/current deep embeddings/i).waitFor({ timeout: 10000 })
  await page.getByText(/every counted sample must also pass the local deep detector/i).waitFor()
  await page.getByRole('button', { name: /^close$/i }).click()
})

await check('admin add student page opens', async () => {
  await page.goto(`${baseUrl}/admin/students/add`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /add new student/i }).waitFor()
  await page.getByText(/capture starts or resumes after one face remains stable/i).waitFor()
})

await check('single-face attendance guard is visible', async () => {
  await page.goto(`${baseUrl}/admin/attendance/live`, { waitUntil: 'domcontentloaded' })
  await page.getByText(/every required frame must contain exactly one continuous face/i).waitFor()
  await page.getByText(/compares maximum, top-3 mean, top-5 mean, and top-5 median scores/i).waitFor()
  await page.getByRole('button', { name: /attendance paused/i }).waitFor()
  await page.getByText(/three fresh quality-gated arcface queries/i).waitFor()
  await page.getByText(/at most two complete fresh retries/i).waitFor()
  await page.getByText(/never fall back to the legacy opencv matcher/i).waitFor()
  await page.getByText(/move_closer-only basic challenge-response/i).waitFor()
  await page.getByText(/after go, move closer and hold until capture finishes/i).waitFor()
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
  await page.getByRole('button', { name: /^logout$/i }).click()
  await page.waitForURL('**/login', { timeout: 10000 })
})

await check('operator login works', async () => {
  await login('operator.cs@fdas.local', 'Operator@12345', '/user/dashboard')
})

await check('operator dashboard opens', async () => {
  await page.getByRole('heading', { name: /department dashboard/i }).waitFor()
  await page.screenshot({ path: path.join(outputDir, '04-operator-dashboard.png'), fullPage: true })
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

if (results.some(([, passed]) => !passed) || pageErrors.length > 0) {
  process.exitCode = 1
}
