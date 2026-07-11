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

await check('/login loads', async () => {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /admin access/i }).waitFor()
  await page.screenshot({ path: path.join(outputDir, '01-login.png'), fullPage: true })
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
  await page.screenshot({ path: path.join(outputDir, '02-admin-dashboard.png'), fullPage: true })
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
  await page.screenshot({ path: path.join(outputDir, '03-operator-dashboard.png'), fullPage: true })
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
