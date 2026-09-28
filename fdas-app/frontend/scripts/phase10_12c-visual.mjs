import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const baseUrl = process.env.FDAS_FRONTEND_BASE_URL || 'http://127.0.0.1:5173'
const captureMode = process.env.FDAS_PHASE10_12C_CAPTURE || 'after'
const outputDir = path.resolve('output/playwright/phase10_12c')
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(15000)
const results = []
const consoleErrors = []
const pageErrors = []

page.on('console', message => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})
page.on('pageerror', error => pageErrors.push(error.message))

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

async function openRoute(route, heading) {
  await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: heading, level: 1 }).waitFor()
  await page.waitForTimeout(450)
}

async function assertLayout(viewportWidth) {
  const measurements = await page.evaluate(() => {
    const root = document.documentElement
    const main = document.querySelector('main')
    return {
      documentScrollWidth: root.scrollWidth,
      documentClientWidth: root.clientWidth,
      mainScrollWidth: main?.scrollWidth || 0,
      mainClientWidth: main?.clientWidth || 0,
    }
  })
  if (measurements.documentScrollWidth > viewportWidth + 1) {
    throw new Error(`document overflow ${measurements.documentScrollWidth}px > ${viewportWidth}px`)
  }
  if (measurements.mainClientWidth && measurements.mainScrollWidth > measurements.mainClientWidth + 1) {
    throw new Error(`main overflow ${measurements.mainScrollWidth}px > ${measurements.mainClientWidth}px`)
  }

  const heading = page.locator('h1').first()
  const header = page.locator('[data-smart-header]')
  if (await heading.count() && await header.count() && await header.getAttribute('data-visible') === 'true') {
    const [headingBox, headerBox] = await Promise.all([heading.boundingBox(), header.boundingBox()])
    if (!headingBox || !headerBox || headingBox.y < headerBox.y + headerBox.height - 1) {
      throw new Error(`page title overlaps sticky header at y=${headingBox?.y}`)
    }
  }
}

async function capture(name) {
  await page.mouse.move(0, 0)
  await page.screenshot({ path: path.join(outputDir, `${name}.png`), animations: 'disabled' })
}

async function assertStudentIdColumn() {
  const table = page.locator('[data-student-table]')
  await table.waitFor({ state: 'visible' })
  const headings = (await table.locator('thead th').allTextContents()).map(value => value.trim())
  if (headings[0] !== 'Student ID' || headings[1] !== 'Name') {
    throw new Error(`unexpected leading student columns: ${headings.slice(0, 2).join(', ')}`)
  }
  if (!headings.includes('Roll No.')) throw new Error('Roll No. column is missing')

  const displayedIds = (await table.locator('[data-student-id]').allTextContents()).map(value => value.trim())
  if (!displayedIds.length) throw new Error('no database student IDs were rendered')
  const invalidId = displayedIds.find(value => !/^#\d+$/.test(value))
  if (invalidId) throw new Error(`student ID is not displayed as #<studentId>: ${invalidId}`)
}

if (captureMode === 'before') {
  await login('admin@fdas.local', 'Admin@12345', '/admin/dashboard')
  await openRoute('/admin/users', /manage users/i)
  await capture('00-manage-users-before-1440')
  console.log('phase10_12c_before_capture=true')
  await browser.close()
  process.exit(0)
}

const adminViews = [
  { slug: 'admin-dashboard', route: '/admin/dashboard', heading: /fdas dashboard/i, primary: /active session/i },
  { slug: 'admin-students', route: '/admin/students', heading: /active students/i, primary: /add student/i },
  { slug: 'admin-users', route: '/admin/users', heading: /manage users/i, primary: /export csv/i },
  { slug: 'admin-classes', route: '/admin/classes', heading: /manage classes/i, primary: /add new class/i },
  { slug: 'admin-attendance', route: '/admin/attendance/live', heading: /attendance marking/i, primary: /start session/i },
  { slug: 'admin-reports', route: '/admin/analytics', heading: /attendance reports/i, primary: /export csv/i },
  { slug: 'account-profile', route: '/account/profile', heading: /account profile/i, primary: /save changes/i },
  { slug: 'account-preferences', route: '/account/preferences', heading: /account preferences/i, primary: /table density/i },
]

await check('admin login', async () => login('admin@fdas.local', 'Admin@12345', '/admin/dashboard'))

await check('Admin navigation and dashboard use Reports terminology', async () => {
  await openRoute('/admin/dashboard', /fdas dashboard/i)
  const reportsLink = page.getByRole('link', { name: /^reports$/i })
  await reportsLink.waitFor({ state: 'visible' })
  if (await reportsLink.getAttribute('href') !== '/admin/analytics') {
    throw new Error('Reports navigation no longer preserves /admin/analytics')
  }
  await page.getByRole('link', { name: /open reports/i }).click()
  await page.waitForURL('**/admin/analytics')
  await page.getByRole('heading', { name: /attendance reports/i, level: 1 }).waitFor()
  if (await page.getByText(/attendance analytics/i).count()) {
    throw new Error('legacy Attendance Analytics wording remains visible')
  }
})

await check('Admin Students shows database IDs before Name and retains Roll No.', async () => {
  await openRoute('/admin/students', /active students/i)
  await assertStudentIdColumn()
})

for (const width of [1440, 1920]) {
  await page.setViewportSize({ width, height: width === 1920 ? 1080 : 1000 })
  for (const view of adminViews) {
    await check(`${view.slug} ${width}px`, async () => {
      await openRoute(view.route, view.heading)
      await assertLayout(width)
      await page.getByText(view.primary).first().waitFor({ state: 'visible' })
      await capture(`${width}-${view.slug}`)
    })
  }

  await check(`admin-inactive-students ${width}px`, async () => {
    await openRoute('/admin/students', /active students/i)
    await page.getByRole('tab', { name: /^inactive students/i }).click()
    await page.getByRole('heading', { name: /inactive students/i, level: 1 }).waitFor()
    await assertLayout(width)
    await capture(`${width}-admin-inactive-students`)
  })
}

await check('Manage Users action hierarchy and SMTP dialog', async () => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await openRoute('/admin/users', /manage users/i)
  const operatorRow = page.getByRole('row').filter({ hasText: 'operator.cs@fdas.local' })
  if (await operatorRow.getByRole('button', { name: /grant all-department access/i }).count()) {
    throw new Error('standalone Grant All action is still present')
  }
  await operatorRow.getByRole('button', { name: /change access/i }).click()
  const accessDialog = page.getByRole('dialog', { name: /change user access/i })
  await accessDialog.getByLabel('Access Scope').selectOption('AllDepartments')
  if (await accessDialog.locator('option[value="AllDepartments"]').count() !== 1) {
    throw new Error('All Departments is unavailable through Change Access')
  }
  await page.keyboard.press('Escape')
  await operatorRow.getByRole('button', { name: /resend approval email/i }).click()
  await page.getByRole('dialog', { name: /resend approval email/i }).waitFor()
  await page.keyboard.press('Escape')
  await page.goto(`${baseUrl}/admin/requests`, { waitUntil: 'domcontentloaded' })
  await page.getByText(/smtp status:/i).waitFor()
})

await check('account menu works', async () => {
  await openRoute('/admin/dashboard', /fdas dashboard/i)
  await page.getByRole('button', { name: /open profile menu/i }).click()
  await page.getByRole('menuitem', { name: /view profile/i }).waitFor({ state: 'visible' })
  await page.keyboard.press('Escape')
})

await check('smart header still hides and reveals', async () => {
  await page.setViewportSize({ width: 1440, height: 720 })
  await openRoute('/admin/students', /active students/i)
  const header = page.locator('[data-smart-header]')
  await page.evaluate(() => { document.scrollingElement.scrollTop = 700 })
  await page.waitForTimeout(350)
  const scrollY = await page.evaluate(() => window.scrollY)
  if (scrollY < 72) throw new Error(`test page did not scroll enough: ${scrollY}px`)
  if (await header.getAttribute('data-visible') !== 'false') throw new Error('header did not hide')
  await page.evaluate(() => { document.scrollingElement.scrollTop -= 180 })
  await page.waitForTimeout(350)
  if (await header.getAttribute('data-visible') !== 'true') throw new Error('header did not reveal')
})

await check('attendance controls remain available', async () => {
  await openRoute('/admin/attendance/live', /attendance marking/i)
  await page.getByRole('button', { name: /start session/i }).waitFor({ state: 'visible' })
  await page.getByRole('button', { name: /stop session/i }).waitFor({ state: 'visible' })
  await page.getByText(/live camera/i).waitFor()
})

await check('operator login', async () => login('operator.cs@fdas.local', 'Operator@12345', '/user/dashboard'))
await check('Operator Students shares the database Student ID column', async () => {
  await openRoute('/user/students', /active students/i)
  await assertStudentIdColumn()
})
const operatorViews = [
  { slug: 'operator-dashboard', route: '/user/dashboard', heading: /department dashboard/i },
  { slug: 'operator-students', route: '/user/students', heading: /active students/i },
  { slug: 'operator-attendance', route: '/user/attendance', heading: /attendance marking/i },
]

for (const width of [1440, 1920]) {
  await page.setViewportSize({ width, height: width === 1920 ? 1080 : 1000 })
  for (const view of operatorViews) {
    await check(`${view.slug} ${width}px`, async () => {
      await openRoute(view.route, view.heading)
      await assertLayout(width)
      await capture(`${width}-${view.slug}`)
    })
  }
}

await check('admin login for responsive audit', async () => login('admin@fdas.local', 'Admin@12345', '/admin/dashboard'))
for (const width of [375, 480, 768, 1024, 1280, 1440, 1920]) {
  await check(`responsive layout ${width}px`, async () => {
    await page.setViewportSize({ width, height: width <= 480 ? 812 : 900 })
    await openRoute('/admin/students', /active students/i)
    await assertLayout(width)
    await page.getByRole('link', { name: /add student/i }).waitFor({ state: 'visible' })
    if (width <= 768) {
      const tableOverflow = await page.locator('[data-student-table]').evaluate(table => ({
        tableWidth: table.scrollWidth,
        wrapperWidth: table.parentElement?.clientWidth || 0,
        wrapperOverflowX: getComputedStyle(table.parentElement).overflowX,
      }))
      if (tableOverflow.tableWidth <= tableOverflow.wrapperWidth) {
        throw new Error(`student table does not overflow its ${tableOverflow.wrapperWidth}px wrapper at ${width}px`)
      }
      if (!['auto', 'scroll'].includes(tableOverflow.wrapperOverflowX)) {
        throw new Error(`student table wrapper cannot scroll horizontally: ${tableOverflow.wrapperOverflowX}`)
      }
    }
  })
}

await check('mobile dashboard screenshot', async () => {
  await page.setViewportSize({ width: 375, height: 812 })
  await openRoute('/admin/dashboard', /fdas dashboard/i)
  await assertLayout(375)
  await capture('375-mobile-dashboard')
})

await check('mobile students screenshot and tabs', async () => {
  await openRoute('/admin/students', /active students/i)
  await page.getByRole('tab', { name: /^inactive students/i }).click()
  await page.getByRole('heading', { name: /inactive students/i, level: 1 }).waitFor()
  await assertLayout(375)
  await capture('375-mobile-students')
})

await check('mobile attendance screenshot', async () => {
  await openRoute('/admin/attendance/live', /attendance marking/i)
  await assertLayout(375)
  await capture('375-mobile-attendance')
})

await check('mobile modal screenshot and keyboard behavior', async () => {
  await openRoute('/admin/classes', /manage classes/i)
  const opener = page.getByRole('button', { name: /add new class/i })
  await opener.click()
  const dialog = page.getByRole('dialog', { name: /add new class/i })
  await dialog.waitFor()
  await capture('375-mobile-modal')
  await page.keyboard.press('Escape')
  await dialog.waitFor({ state: 'detached' })
})

await check('browser runtime stayed clean', async () => {
  if (pageErrors.length) throw new Error(`page errors: ${pageErrors.join(' | ')}`)
  if (consoleErrors.length) throw new Error(`console errors: ${consoleErrors.join(' | ')}`)
})

await browser.close()
const failures = results.filter(([, passed]) => !passed)
console.log(`phase10_12c_browser_checks=${results.length}`)
console.log(`phase10_12c_browser_failures=${failures.length}`)
if (failures.length) process.exitCode = 1
