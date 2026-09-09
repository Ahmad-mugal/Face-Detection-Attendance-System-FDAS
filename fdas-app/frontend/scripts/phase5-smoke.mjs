import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const baseUrl = 'http://127.0.0.1:5173'
const outputDir = path.resolve('output/playwright')
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(8000)
const consoleErrors = []
const pageErrors = []
const results = []
const unavailableMessage = 'Unable to connect to the FDAS server. Please make sure the backend is running.'
const browserRegistrationEmail = 'phase10.4.browser@fdas.local'

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

await check('admin add student page opens', async () => {
  await page.goto(`${baseUrl}/admin/students/add`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /add new student/i }).waitFor()
})

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
