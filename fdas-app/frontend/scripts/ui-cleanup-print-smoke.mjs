import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

if (process.env.FDAS_UI_CLEANUP_ISOLATED !== '1') {
  throw new Error('UI cleanup browser verification requires an isolated backend.')
}

const baseUrl = process.env.FDAS_FRONTEND_BASE_URL || 'http://127.0.0.1:5173'
const outputDir = path.resolve('output/playwright/ui_cleanup_print')
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(20000)
const results = []
const pageErrors = []
const consoleErrors = []

page.on('pageerror', error => pageErrors.push(error.message))
page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })

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

async function openReport(route, heading) {
  await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: heading, level: 1 }).waitFor()
  await page.locator('[data-print-report-table] tbody tr').first().waitFor()
  await page.getByRole('button', { name: 'Print', exact: true }).waitFor()
  await page.getByRole('button', { name: 'Export CSV', exact: true }).waitFor()
  await page.getByRole('button', { name: 'Refresh', exact: true }).waitFor()
}

async function assertPrintInvocation() {
  await page.evaluate(() => {
    window.__fdasPrintCalls = 0
    window.print = () => { window.__fdasPrintCalls += 1 }
  })
  await page.getByRole('button', { name: 'Print', exact: true }).click()
  await page.waitForFunction(() => window.__fdasPrintCalls === 1)
}

async function assertPrintLayout() {
  await page.emulateMedia({ media: 'print' })
  try {
    const layout = await page.evaluate(() => {
      const report = document.querySelector('.fdas-print-report')
      const meta = document.querySelector('[data-print-report-meta]')
      const table = document.querySelector('[data-print-report-table]')
      const firstRow = table?.querySelector('tbody tr')
      const header = document.querySelector('[data-smart-header]')
      return {
        reportVisibility: report ? getComputedStyle(report).visibility : null,
        metaDisplay: meta ? getComputedStyle(meta).display : null,
        headerVisibility: header ? getComputedStyle(header).visibility : null,
        tableWidth: table?.getBoundingClientRect().width || 0,
        viewportWidth: document.documentElement.clientWidth,
        theadDisplay: table?.tHead ? getComputedStyle(table.tHead).display : null,
        rowBreakInside: firstRow ? getComputedStyle(firstRow).breakInside : null,
        visiblePrintButton: [...document.querySelectorAll('button')].some(button => (
          button.textContent.trim() === 'Print'
          && button.getClientRects().length > 0
          && getComputedStyle(button).visibility !== 'hidden'
        )),
      }
    })
    if (layout.reportVisibility !== 'visible' || layout.metaDisplay === 'none') throw new Error('print report metadata is not visible')
    if (layout.headerVisibility !== 'hidden') throw new Error('authenticated header remains visible in print layout')
    if (layout.visiblePrintButton) throw new Error('Print control remains visible in print layout')
    if (layout.tableWidth > layout.viewportWidth + 1) throw new Error('print table overflows the printable viewport')
    if (layout.theadDisplay !== 'table-header-group') throw new Error('table header is not configured to repeat')
    if (!['avoid', 'avoid-page'].includes(layout.rowBreakInside)) throw new Error(`rows may split across pages: ${layout.rowBreakInside}`)
    await page.screenshot({ path: path.join(outputDir, '06-admin-report-print-layout.png'), fullPage: true, animations: 'disabled' })
  } finally {
    await page.emulateMedia({ media: 'screen' })
  }
}

await check('Admin report exposes Print beside Export and prints the current report view', async () => {
  await login('admin@fdas.local', 'Admin@12345', '/admin/dashboard')
  await openReport('/admin/analytics', /attendance reports/i)
  await page.getByRole('button', { name: 'Settings', exact: true }).waitFor()
  const buttons = page.locator('.fdas-page-actions button')
  if (await buttons.nth(0).textContent() !== 'Print' || await buttons.nth(1).textContent() !== 'Export CSV') throw new Error('Print is not positioned beside Export CSV')
  await page.screenshot({ path: path.join(outputDir, '01-admin-report-print-export.png'), fullPage: true, animations: 'disabled' })
  await assertPrintInvocation()
  await assertPrintLayout()
})

await check('Manage Users actions remain separated and scroll safely at all required widths', async () => {
  for (const width of [375, 480, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: width <= 480 ? 812 : 1000 })
    await page.goto(`${baseUrl}/admin/users`, { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: /manage users/i, level: 1 }).waitFor()
    const tableWrap = page.locator('.fdas-table-wrap')
    await tableWrap.evaluate(element => { element.scrollLeft = element.scrollWidth })
    const metrics = await page.locator('.fdas-user-actions').first().evaluate(element => ({
      gap: parseFloat(getComputedStyle(element).gap),
      minControlHeight: Math.min(...[...element.querySelectorAll('button')].map(button => button.getBoundingClientRect().height)),
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
    }))
    const wrapperScrolls = await tableWrap.evaluate(element => element.scrollWidth > element.clientWidth)
    if (metrics.gap < 8) throw new Error(`action gap is ${metrics.gap}px at ${width}px`)
    if (metrics.minControlHeight < 36) throw new Error(`action target is ${metrics.minControlHeight}px high at ${width}px`)
    if (metrics.documentWidth > metrics.viewportWidth + 1) throw new Error(`document overflows at ${width}px`)
    if (width < 1320 && !wrapperScrolls) throw new Error(`table does not provide horizontal scrolling at ${width}px`)
    if (width === 768) await page.screenshot({ path: path.join(outputDir, '04-manage-users-narrow-768.png'), fullPage: true, animations: 'disabled' })
    if (width === 1440) await page.screenshot({ path: path.join(outputDir, '03-manage-users-wide-1440.png'), fullPage: true, animations: 'disabled' })
  }
})

await check('Operator report stays department-scoped and retains Print plus Export', async () => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await login('operator.cs@fdas.local', 'Operator@12345', '/user/dashboard')
  await openReport('/user/reports', /^reports$/i)
  if (await page.getByLabel('Department').count()) throw new Error('department-only Operator can choose another department')
  const departments = await page.locator('[data-print-report-table] tbody tr td:nth-child(2)').allTextContents()
  if (departments.some(value => value.trim() !== 'Computer Science')) throw new Error('Operator report contains another department')
  await page.screenshot({ path: path.join(outputDir, '02-operator-report-print-export.png'), fullPage: true, animations: 'disabled' })
  await assertPrintInvocation()
})

await check('Operator header removes only the standalone gear and keeps account preferences', async () => {
  if (await page.getByRole('button', { name: 'Settings', exact: true }).count()) throw new Error('standalone Settings gear still exists')
  const profile = page.getByRole('button', { name: /open profile menu/i })
  await profile.click()
  await page.getByRole('menuitem', { name: 'Account Preferences', exact: true }).waitFor()
  await page.screenshot({ path: path.join(outputDir, '05-operator-header-without-standalone-gear.png'), fullPage: false, animations: 'disabled' })
})

await check('browser runtime stayed clean', async () => {
  if (pageErrors.length) throw new Error(`page errors: ${pageErrors.join(' | ')}`)
  if (consoleErrors.length) throw new Error(`console errors: ${consoleErrors.join(' | ')}`)
})

await browser.close()
const failures = results.filter(([, passed]) => !passed)
console.log(`ui_cleanup_browser_checks=${results.length}`)
console.log(`ui_cleanup_browser_failures=${failures.length}`)
console.log(`page_errors=${pageErrors.length}`)
console.log(`console_errors=${consoleErrors.length}`)
if (failures.length) process.exitCode = 1
