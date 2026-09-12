import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const baseUrl = process.env.FDAS_FRONTEND_BASE_URL || 'http://127.0.0.1:5173'
const outputDir = path.resolve('output/playwright')
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(10000)
const failures = []
const pageErrors = []
page.on('pageerror', error => pageErrors.push(error.message))

async function check(name, assertion) {
  try {
    await assertion()
    console.log(`${name}=true`)
  } catch (error) {
    failures.push(`${name}: ${error.message}`)
    console.log(`${name}=false :: ${error.message}`)
  }
}

await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
await page.getByLabel('Email').fill('admin@fdas.local')
await page.locator('#password').fill('Admin@12345')
await page.getByRole('button', { name: /sign in/i }).click()
await page.waitForURL('**/admin/dashboard')
await page.goto(`${baseUrl}/admin/students`, { waitUntil: 'domcontentloaded' })
await page.getByRole('heading', { name: /all students/i }).waitFor()

const duplicateRow = page.getByRole('row').filter({ hasText: 'CS-2022-58' })
const canonicalRow = page.getByRole('row').filter({ hasText: 'cs-2026-789' })

await check('inactive_duplicate_19_has_no_diagnostic_action', async () => {
  if (await duplicateRow.getByRole('button', { name: /independent deep recognition diagnostic/i }).count() !== 0) {
    throw new Error('Inactive duplicate #19 still exposes a diagnostic action')
  }
})

await check('canonical_22_has_diagnostic_action', async () => {
  await canonicalRow.getByRole('button', { name: /independent deep recognition diagnostic/i }).waitFor()
})

await canonicalRow.getByRole('button', { name: /independent deep recognition diagnostic/i }).click()

await check('diagnostic_modal_opens_for_22', async () => {
  await page.getByRole('heading', { name: /independent deep recognition test/i }).waitFor()
  await page.getByText('Ahmad Mughal — cs-2026-789', { exact: true }).waitFor()
})

await check('diagnostic_no_persistence_notice_visible', async () => {
  await page.getByText(/images are not saved as templates, embeddings, recovery samples, or attendance evidence/i).waitFor()
})

await check('ten_query_design_visible', async () => {
  await page.getByText('Progress: 0/10').waitFor()
  await page.getByText(/frontal.*look naturally at the camera/i).waitFor()
})

await check('capture_disabled_until_camera_starts', async () => {
  const captureButton = page.getByRole('button', { name: /capture query 1/i })
  if (!(await captureButton.isDisabled())) throw new Error('Capture was enabled before camera startup')
})

await page.screenshot({ path: path.join(outputDir, 'phase10_7d-diagnostic-modal.png'), fullPage: true })
await page.getByRole('button', { name: /^close$/i }).click()
await browser.close()

console.log(`page_errors=${pageErrors.length}`)
if (pageErrors.length > 0) failures.push(...pageErrors.map(error => `page error: ${error}`))
if (failures.length > 0) {
  failures.forEach(failure => console.error(failure))
  process.exitCode = 1
}
