import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

if (process.env.FDAS_PHASE10_12B_ISOLATED !== '1') {
  throw new Error('Phase 10.12B browser verification includes status mutations and requires an isolated backend.')
}

const baseUrl = process.env.FDAS_FRONTEND_BASE_URL || 'http://127.0.0.1:5173'
const outputDir = path.resolve('output/playwright/phase10_12b')
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } })
page.setDefaultTimeout(12000)
const results = []
const consoleErrors = []
const pageErrors = []
const nativeDialogs = []

page.on('console', message => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})
page.on('pageerror', error => pageErrors.push(error.message))
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

async function login(email, password, expectedPath) {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill(email)
  await page.locator('#password').fill(password)
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(`**${expectedPath}`)
}

async function expectNoHorizontalOverflow(viewportWidth) {
  const width = await page.evaluate(() => document.documentElement.scrollWidth)
  if (width > viewportWidth) throw new Error(`horizontal overflow: ${width}px > ${viewportWidth}px`)
}

await check('admin login', async () => login('admin@fdas.local', 'Admin@12345', '/admin/dashboard'))

await check('Add Class typing, focus trap, Escape, and cleanup', async () => {
  await page.goto(`${baseUrl}/admin/classes`, { waitUntil: 'domcontentloaded' })
  const opener = page.getByRole('button', { name: /add new class/i })
  await opener.click()
  const dialog = page.getByRole('dialog', { name: /add new class/i })
  const className = dialog.getByLabel('Class Name')
  await className.waitFor()
  await className.pressSequentially('BSCS Semester 67')
  await className.press('Backspace')
  if (await className.inputValue() !== 'BSCS Semester 6') throw new Error('complete typed value was not retained')
  if (!(await className.evaluate(element => element === document.activeElement))) throw new Error('focus left Class Name while typing')
  await page.screenshot({ path: path.join(outputDir, '01-add-class-typed.png') })

  const focusable = dialog.locator('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')
  const first = focusable.first()
  const last = focusable.last()
  await first.focus()
  await page.keyboard.press('Shift+Tab')
  if (!(await last.evaluate(element => element === document.activeElement))) throw new Error('Shift+Tab did not wrap to the last dialog control')
  await page.keyboard.press('Tab')
  if (!(await first.evaluate(element => element === document.activeElement))) throw new Error('Tab did not wrap to the first dialog control')

  await page.keyboard.press('Escape')
  await dialog.waitFor({ state: 'detached' })
  if (await page.locator('.fdas-modal-backdrop').count()) throw new Error('modal backdrop remained after Escape')
  if (await page.evaluate(() => document.body.style.overflow) === 'hidden') throw new Error('body remained scroll locked')
  await page.waitForFunction(element => element === document.activeElement, await opener.elementHandle())
  await opener.click()
  await page.getByRole('dialog', { name: /add new class/i }).waitFor()
  await page.keyboard.press('Escape')
})

await check('Add Student page retains normal typing', async () => {
  await page.goto(`${baseUrl}/admin/students/add`, { waitUntil: 'domcontentloaded' })
  const fullName = page.getByLabel('Full Name')
  await fullName.fill('')
  await fullName.pressSequentially('Student Test 19X')
  await fullName.press('Backspace')
  if (await fullName.inputValue() !== 'Student Test 19') throw new Error('Add Student typing was disrupted')
  if (!(await fullName.evaluate(element => element === document.activeElement))) throw new Error('Add Student input lost focus')
})

let inactiveStudentRoll = ''
await check('Active and Inactive Students views, searches, and screenshots', async () => {
  await page.goto(`${baseUrl}/admin/students`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Active Students', level: 1 }).waitFor()
  await page.locator('tbody tr').first().waitFor()
  await page.getByRole('tab', { name: /^active students/i }).getAttribute('aria-selected').then(value => {
    if (value !== 'true') throw new Error('Active Students is not the default tab')
  })
  if (await page.getByText('Inactive', { exact: true }).count()) throw new Error('inactive rows leaked into the Active view')
  await page.screenshot({ path: path.join(outputDir, '02-active-students.png'), fullPage: true })

  const activeRow = page.locator('tbody tr').first()
  const activeRoll = (await activeRow.locator('td').nth(1).innerText()).trim()
  const activeSearch = page.getByLabel('Search active students')
  await activeSearch.fill(activeRoll)
  if (await page.locator('tbody tr').count() !== 1) throw new Error('Active search did not filter independently')

  await page.getByRole('tab', { name: /^inactive students/i }).click()
  await page.getByRole('heading', { name: 'Inactive Students', level: 1 }).waitFor()
  const inactiveRows = page.locator('tbody tr')
  if (await inactiveRows.count() < 1) throw new Error('Inactive Students view is empty')
  const statusBadges = page.getByText('Inactive', { exact: true })
  if (await statusBadges.count() < 1) throw new Error('Inactive status badge is missing')
  inactiveStudentRoll = (await inactiveRows.first().locator('td').nth(1).innerText()).trim()
  const inactiveSearch = page.getByLabel('Search inactive students')
  await inactiveSearch.fill(inactiveStudentRoll)
  if (await page.locator('tbody tr').count() !== 1) throw new Error('Inactive search did not filter independently')
  await page.screenshot({ path: path.join(outputDir, '03-inactive-students.png'), fullPage: true })
})

await check('Reactivate moves disposable student to Active view', async () => {
  const inactiveRow = page.locator('tbody tr').filter({ hasText: inactiveStudentRoll })
  await inactiveRow.getByRole('button', { name: /reactivate/i }).click()
  const dialog = page.getByRole('dialog', { name: /reactivate student/i })
  await dialog.waitFor()
  await page.screenshot({ path: path.join(outputDir, '04-reactivate-confirmation.png') })
  const backdropZ = await page.locator('.fdas-modal-backdrop').evaluate(element => Number(getComputedStyle(element).zIndex))
  const headerZ = await page.locator('[data-smart-header]').evaluate(element => Number(getComputedStyle(element).zIndex))
  if (backdropZ <= headerZ) throw new Error('modal layer is not above the smart header')
  await dialog.getByRole('button', { name: 'Reactivate Student', exact: true }).click()
  await dialog.waitFor({ state: 'detached' })
  await page.getByText('Student reactivated successfully.').waitFor()
  if (await page.locator('tbody tr').filter({ hasText: inactiveStudentRoll }).count()) throw new Error('reactivated student remained in Inactive view')
  await page.getByRole('tab', { name: /^active students/i }).click()
  await page.getByLabel('Search active students').fill(inactiveStudentRoll)
  await page.locator('tbody tr').filter({ hasText: inactiveStudentRoll }).waitFor()
})

await check('Admin Edit Student modal typing remains focused', async () => {
  const row = page.locator('tbody tr').filter({ hasText: inactiveStudentRoll })
  await row.getByRole('button', { name: /edit/i }).first().click()
  const dialog = page.getByRole('dialog', { name: /edit student/i })
  const input = dialog.getByLabel('Full name')
  await input.fill('')
  await input.pressSequentially('Admin Test 42X')
  await input.press('Backspace')
  if (await input.inputValue() !== 'Admin Test 42') throw new Error('Admin Edit Student typing was disrupted')
  if (!(await input.evaluate(element => element === document.activeElement))) throw new Error('Admin Edit Student focus jumped')
  await page.keyboard.press('Escape')
})

await check('SMTP capability UI is safe and visible', async () => {
  await page.goto(`${baseUrl}/admin/requests`, { waitUntil: 'domcontentloaded' })
  await page.getByText(/smtp status:/i).waitFor()
  if (await page.getByText(/FDAS_SMTP_PASSWORD|app password/i).count()) throw new Error('SMTP secret material appeared in the UI')
})

await check('Admin smart header hides down, reveals up, and resets on route change', async () => {
  await page.goto(`${baseUrl}/admin/students`, { waitUntil: 'domcontentloaded' })
  const header = page.locator('[data-smart-header]')
  await page.locator('tbody tr').first().waitFor()
  if (await header.getAttribute('data-visible') !== 'true') throw new Error('header was not visible at top')
  await page.screenshot({ path: path.join(outputDir, '05-header-visible-top.png') })
  await page.evaluate(() => { document.scrollingElement.scrollTop = 700 })
  await page.waitForTimeout(350)
  const scrollState = await page.evaluate(() => ({ y: window.scrollY, height: document.documentElement.scrollHeight, viewport: window.innerHeight }))
  if (scrollState.y < 72) throw new Error(`admin page did not scroll enough: ${JSON.stringify(scrollState)}`)
  if (await header.getAttribute('data-visible') !== 'false') throw new Error(`header did not hide on downward scroll: ${JSON.stringify(scrollState)}`)
  const hiddenBox = await header.boundingBox()
  if (!hiddenBox || hiddenBox.y > -Math.max(8, hiddenBox.height * 0.75)) throw new Error(`hidden header remained visible at y=${hiddenBox?.y}`)
  await page.evaluate(() => { document.scrollingElement.scrollTop -= 180 })
  await page.waitForTimeout(350)
  if (await header.getAttribute('data-visible') !== 'true') throw new Error('header did not reveal on upward scroll')
  const revealedBox = await header.boundingBox()
  if (!revealedBox || revealedBox.y < -1 || revealedBox.y > 1) throw new Error(`revealed header was off-screen at y=${revealedBox?.y}`)
  await page.screenshot({ path: path.join(outputDir, '06-header-revealed-up.png') })
  await page.goto(`${baseUrl}/admin/classes`, { waitUntil: 'domcontentloaded' })
  if (await page.locator('[data-smart-header]').getAttribute('data-visible') !== 'true') throw new Error('route change did not reset header visibility')
})

await check('Admin mobile Students is responsive', async () => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto(`${baseUrl}/admin/students`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Active Students', level: 1 }).waitFor()
  await page.locator('tbody tr').first().waitFor()
  await page.waitForTimeout(450)
  await expectNoHorizontalOverflow(375)
  await page.screenshot({ path: path.join(outputDir, '07-admin-mobile-students.png'), fullPage: true })
})

await check('Operator modal, scope, smart header, and mobile Students', async () => {
  await page.setViewportSize({ width: 480, height: 850 })
  await login('operator.cs@fdas.local', 'Operator@12345', '/user/dashboard')
  await page.goto(`${baseUrl}/user/students`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Active Students', level: 1 }).waitFor()
  await page.locator('tbody tr').first().waitFor()
  await page.waitForTimeout(450)
  await expectNoHorizontalOverflow(480)
  await page.screenshot({ path: path.join(outputDir, '08-operator-mobile-students.png'), fullPage: true })

  const edit = page.getByRole('button', { name: /^edit /i }).first()
  await edit.click()
  const dialog = page.getByRole('dialog', { name: /edit student/i })
  const input = dialog.getByLabel('Full name')
  await input.fill('')
  await input.pressSequentially('Operator Test 7X')
  await input.press('Backspace')
  if (await input.inputValue() !== 'Operator Test 7') throw new Error('Operator modal typing was disrupted')
  if (!(await input.evaluate(element => element === document.activeElement))) throw new Error('Operator modal focus jumped')
  await page.keyboard.press('Escape')

  const main = page.locator('main')
  await main.evaluate(element => { element.scrollTop = 700 })
  await page.waitForTimeout(350)
  const header = page.locator('[data-smart-header]')
  if (await header.getAttribute('data-visible') !== 'false') throw new Error('operator header did not hide on downward content scroll')
  await main.evaluate(element => { element.scrollTop -= 180 })
  await page.waitForTimeout(350)
  if (await header.getAttribute('data-visible') !== 'true') throw new Error('operator header did not reveal on upward content scroll')
})

await check('browser infrastructure stayed clean', async () => {
  if (nativeDialogs.length) throw new Error(`native dialogs: ${nativeDialogs.join(' | ')}`)
  if (pageErrors.length) throw new Error(`page errors: ${pageErrors.join(' | ')}`)
  if (consoleErrors.length) throw new Error(`console errors: ${consoleErrors.join(' | ')}`)
})

await browser.close()

const failures = results.filter(([, passed]) => !passed)
console.log(`phase10_12b_browser_checks=${results.length}`)
console.log(`phase10_12b_browser_failures=${failures.length}`)
if (failures.length) process.exitCode = 1
