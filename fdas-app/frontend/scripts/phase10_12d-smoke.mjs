import { chromium } from 'playwright'
import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'

if (process.env.FDAS_PHASE10_12D_ISOLATED !== '1') {
  throw new Error('Phase 10.12D browser verification mutates users/students and requires an isolated backend.')
}

const baseUrl = process.env.FDAS_FRONTEND_BASE_URL || 'http://127.0.0.1:5173'
const apiUrl = process.env.FDAS_API_BASE_URL || 'http://127.0.0.1:8000'
const outputDir = path.resolve('output/playwright/phase10_12d')
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(15000)
const results = []
const pageErrors = []
const nativeDialogs = []
const consoleErrors = []
const expectedConsoleErrors = []
const stamp = Date.now()
const requestOneEmail = `phase12d.request.one.${stamp}@example.local`
const requestTwoEmail = `phase12d.request.two.${stamp}@example.local`
const validRollOne = `P12D-${stamp}-A`
const validRollTwo = `P12D-${stamp}-B`

page.on('pageerror', error => pageErrors.push(error.message))
page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('dialog', async dialog => { nativeDialogs.push(`${dialog.type()}: ${dialog.message()}`); await dialog.dismiss() })

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

async function token() {
  return page.evaluate(() => localStorage.getItem('fdas_access_token'))
}

async function authHeaders(value = null) {
  return { Authorization: `Bearer ${value || await token()}` }
}

async function registerRequest(email, fullName, departmentId) {
  const response = await page.request.post(`${apiUrl}/api/auth/register-request`, {
    data: { fullName, email, password: 'Browser-Test-123', requestedDepartmentId: departmentId },
  })
  if (!response.ok()) throw new Error(`registration fixture failed: ${response.status()} ${await response.text()}`)
  return response.json()
}

await check('login icon geometry and responsive spacing', async () => {
  for (const width of [375, 480, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: width <= 480 ? 812 : 1000 })
    await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
    const geometry = await page.locator('#email').evaluate(input => {
      const wrapper = input.parentElement
      const icon = wrapper.querySelector('.fdas-auth-leading-icon')
      const style = getComputedStyle(input)
      return { paddingLeft: parseFloat(style.paddingLeft), iconWidth: icon.getBoundingClientRect().width, documentWidth: document.documentElement.scrollWidth }
    })
    const passwordGeometry = await page.locator('#password').evaluate(input => {
      const wrapper = input.parentElement
      return { paddingRight: parseFloat(getComputedStyle(input).paddingRight), trailingWidth: wrapper.querySelector('.fdas-auth-trailing-action').getBoundingClientRect().width }
    })
    if (geometry.paddingLeft < geometry.iconWidth || passwordGeometry.paddingRight < passwordGeometry.trailingWidth) throw new Error(`auth icon overlap risk at ${width}px`)
    if (geometry.documentWidth > width) throw new Error(`login overflow at ${width}px`)
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email').fill('admin@fdas.local')
  await page.locator('#password').fill('Admin@12345')
  await page.screenshot({ path: path.join(outputDir, '02-login-input-icon-alignment.png') })
})

const departmentResponse = await page.request.get(`${apiUrl}/api/auth/registration-departments`)
const departments = await departmentResponse.json()
const csDepartment = departments.find(item => item.departmentName === 'Computer Science') || departments[0]
await registerRequest(requestOneEmail, 'Phase 12D Request One', csDepartment.departmentId)

await check('admin notification badge, list, read, action navigation, and mark all', async () => {
  await login('admin@fdas.local', 'Admin@12345', '/admin/dashboard')
  await page.getByRole('button', { name: /open notifications, .* unread/i }).waitFor()
  await page.getByRole('button', { name: /open notifications/i }).click()
  const center = page.getByRole('dialog', { name: 'Notifications' })
  const newestRegistration = center.locator('article').filter({ hasText: 'New operator registration request' }).first()
  await newestRegistration.waitFor()
  await newestRegistration.locator('time').filter({ hasText: 'Just now' }).waitFor()
  await page.screenshot({ path: path.join(outputDir, '01-notification-dropdown-unread.png') })
  await center.getByRole('button', { name: 'Open' }).first().click()
  await page.waitForURL('**/admin/requests')
  await registerRequest(requestTwoEmail, 'Phase 12D Request Two', csDepartment.departmentId)
  await page.getByRole('button', { name: /open notifications/i }).click()
  await center.getByText('New operator registration request').first().waitFor()
  await center.getByRole('button', { name: /mark all read/i }).click()
  await page.getByText('You are all caught up').waitFor()
})

let adminToken = ''
await check('Manage Users removes Grant All, preserves All Departments, and exposes safe delete', async () => {
  adminToken = await token()
  await page.goto(`${baseUrl}/admin/users`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Manage Users' }).waitFor()
  if (await page.getByTitle(/grant all-department/i).count()) throw new Error('standalone Grant All control still exists')
  const operatorRow = page.locator('tbody tr').filter({ hasText: 'operator.cs@fdas.local' })
  await operatorRow.getByRole('button', { name: 'Change Access' }).click()
  const accessDialog = page.getByRole('dialog', { name: 'Change User Access' })
  await accessDialog.getByLabel('Access Scope').selectOption('AllDepartments')
  if (await accessDialog.locator('option[value="AllDepartments"]').count() !== 1) throw new Error('All Departments option is missing from Change Access')
  await accessDialog.getByRole('button', { name: 'Cancel' }).click()
  const adminRow = page.locator('tbody tr').filter({ hasText: 'admin@fdas.local' })
  if (!(await adminRow.getByRole('button', { name: /protected administrator/i }).isDisabled())) throw new Error('protected Admin delete was enabled')
  await operatorRow.getByRole('button', { name: /resend approval email/i }).waitFor()
  await page.screenshot({ path: path.join(outputDir, '03-manage-users-refined-actions.png') })
  const disposableRow = page.locator('tbody tr').filter({ hasText: requestTwoEmail })
  await disposableRow.getByRole('button', { name: /delete phase 12d request two/i }).click()
  const deleteDialog = page.getByRole('dialog', { name: 'Delete User?' })
  await deleteDialog.waitFor()
  await page.screenshot({ path: path.join(outputDir, '04-delete-user-confirmation.png') })
  await deleteDialog.getByRole('button', { name: 'Delete User', exact: true }).click()
  await page.getByText('User permanently deleted.').waitFor()
})

const csvContent = [
  'Name,Email,Roll Number,Department,Class',
  `Phase Import One,phase.import.one.${stamp}@example.com,${validRollOne},Computer Science,BSCS Semester 5 - A`,
  `Phase Import Two,phase.import.two.${stamp}@example.com,${validRollTwo},Computer Science,BSCS Semester 5 - A`,
  `Duplicate Roll,phase.import.duplicate.${stamp}@example.com,${validRollTwo},Computer Science,BSCS Semester 5 - A`,
  `Unknown Department,phase.import.invalid.${stamp}@example.com,P12D-${stamp}-BAD,Computer Sciense,BSCS Semester 5 - A`,
].join('\n')

await check('CSV template download and four-step import flow', async () => {
  await page.goto(`${baseUrl}/admin/students`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Active Students', level: 1 }).waitFor()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: /csv template/i }).click()
  const download = await downloadPromise
  const downloadedContent = await readFile(await download.path(), 'utf8')
  if (!download.suggestedFilename().includes('FDAS_Student_Import_Template.csv') || !downloadedContent.includes('Name,Email,Roll Number,Department,Class')) throw new Error('downloaded template drifted')

  await page.getByRole('button', { name: /import students/i }).click()
  const importDialog = page.getByRole('dialog', { name: 'Import Students' })
  await importDialog.waitFor()
  await page.screenshot({ path: path.join(outputDir, '06-import-upload-step.png') })
  await importDialog.locator('input[type=file]').setInputFiles({ name: 'phase10_12d_students.csv', mimeType: 'text/csv', buffer: Buffer.from(csvContent) })
  await importDialog.getByRole('button', { name: 'Validate CSV' }).click()
  await importDialog.locator('[data-import-step=preview]').waitFor()
  await importDialog.getByText('Duplicate', { exact: true }).first().waitFor()
  await importDialog.getByText('Invalid', { exact: true }).first().waitFor()
  await page.screenshot({ path: path.join(outputDir, '07-import-validation-preview.png') })
  const errorDownloadPromise = page.waitForEvent('download')
  await importDialog.getByRole('button', { name: /download error report/i }).click()
  const errorDownload = await errorDownloadPromise
  if (!errorDownload.suggestedFilename().includes('FDAS_Student_Import_Errors.csv')) throw new Error('error report was not downloaded')
  await importDialog.getByRole('button', { name: 'Import 2 Valid Students' }).click()
  await importDialog.locator('[data-import-step=complete]').waitFor()
  await importDialog.getByText('Students imported successfully.').waitFor()
  await page.screenshot({ path: path.join(outputDir, '08-import-completed-state.png') })
  await importDialog.getByRole('button', { name: 'Done' }).click()
})

await check('imported student is Pending Face Registration and reuses enrollment', async () => {
  const search = page.getByLabel('Search active students')
  await search.fill(validRollOne)
  const row = page.locator('tbody tr').filter({ hasText: validRollOne })
  await row.getByText('Pending Face Registration').waitFor()
  await row.getByRole('button', { name: /register face/i }).waitFor()
  await row.getByRole('button', { name: /delete phase import one/i }).waitFor()
  await page.screenshot({ path: path.join(outputDir, '09-student-pending-face-registration.png') })
  await page.screenshot({ path: path.join(outputDir, '05-student-delete-register-actions.png') })
  await row.getByRole('button', { name: /register face/i }).click()
  const enrollment = page.getByRole('dialog', { name: 'Register Student Face' })
  await enrollment.getByRole('heading', { name: 'Face Enrollment', exact: true }).waitFor()
  if (await enrollment.getByLabel('Full Name').count()) throw new Error('enrollment incorrectly asks for student profile fields')
  await page.screenshot({ path: path.join(outputDir, '10-imported-student-face-registration-launch.png') })
  await enrollment.getByRole('button', { name: /close register student face/i }).click()
})

await check('safe student delete and protected-history blocking work in UI', async () => {
  await page.getByLabel('Search active students').fill(validRollOne)
  let row = page.locator('tbody tr').filter({ hasText: validRollOne })
  await row.getByRole('button', { name: /delete phase import one/i }).click()
  await page.getByRole('dialog', { name: 'Delete Student?' }).getByRole('button', { name: 'Delete Student', exact: true }).click()
  await page.getByText('Student permanently deleted.').waitFor()

  const attendanceResponse = await page.request.get(`${apiUrl}/api/attendance-records`, { headers: await authHeaders(adminToken) })
  const attendance = await attendanceResponse.json()
  if (!attendance.length) throw new Error('no attendance fixture available')
  const protectedStudentResponse = await page.request.get(`${apiUrl}/api/students/${attendance[0].studentId}`, { headers: await authHeaders(adminToken) })
  const protectedStudent = await protectedStudentResponse.json()
  await page.goto(`${baseUrl}/admin/students`, { waitUntil: 'domcontentloaded' })
  if (protectedStudent.status !== 'Active') await page.getByRole('tab', { name: /^inactive students/i }).click()
  const protectedSearch = page.getByLabel(`Search ${protectedStudent.status === 'Active' ? 'active' : 'inactive'} students`)
  await protectedSearch.fill(protectedStudent.rollNo)
  row = page.locator('tbody tr').filter({ hasText: protectedStudent.rollNo })
  await row.getByRole('button', { name: new RegExp(`delete ${protectedStudent.fullName}`, 'i') }).click()
  const consoleCheckpoint = consoleErrors.length
  await page.getByRole('dialog', { name: 'Delete Student?' }).getByRole('button', { name: 'Delete Student', exact: true }).click()
  await page.getByText(/historical records and cannot be permanently deleted/i).waitFor()
  const protectedDeleteErrors = consoleErrors.splice(consoleCheckpoint)
  for (const error of protectedDeleteErrors) {
    if (error.includes('409 (Conflict)')) expectedConsoleErrors.push(error)
    else consoleErrors.push(error)
  }
})

await check('operator sees only scoped/private notifications and unauthorized CSV row is invalid', async () => {
  const usersResponse = await page.request.get(`${apiUrl}/api/admin/users`, { headers: await authHeaders(adminToken) })
  const users = await usersResponse.json()
  const operator = users.find(user => user.email === 'operator.cs@fdas.local')
  const update = await page.request.patch(`${apiUrl}/api/admin/users/${operator.userId}/access`, {
    headers: await authHeaders(adminToken),
    data: { accessScope: 'Department', assignedDepartmentId: csDepartment.departmentId },
  })
  if (!update.ok()) throw new Error('operator notification fixture failed')

  await page.evaluate(() => localStorage.removeItem('fdas_access_token'))
  await login('operator.cs@fdas.local', 'Operator@12345', '/user/dashboard')
  await page.getByRole('button', { name: /open notifications/i }).click()
  const center = page.getByRole('dialog', { name: 'Notifications' })
  await center.getByText('Access scope changed').waitFor()
  if (await center.getByText('New operator registration request').count()) throw new Error('operator received Admin-only notification')

  const operatorToken = await token()
  const unauthorizedCsv = 'Name,Email,Roll Number,Department,Class\nUnauthorized Student,unauthorized.browser@example.com,IT-BROWSER-001,IT,BSIT Semester 3 - A\n'
  const validation = await page.request.post(`${apiUrl}/api/students/import/validate`, {
    headers: await authHeaders(operatorToken),
    multipart: { file: { name: 'unauthorized.csv', mimeType: 'text/csv', buffer: Buffer.from(unauthorizedCsv) } },
  })
  const validationBody = await validation.json()
  if (!validation.ok() || validationBody.rows[0].status !== 'Invalid' || !validationBody.rows[0].issues.includes('Unauthorized Department')) throw new Error('operator department scope was not enforced')
})

await check('mobile notification dropdown and import flow are contained', async () => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto(`${baseUrl}/user/dashboard`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /open notifications/i }).click()
  const popover = page.getByRole('dialog', { name: 'Notifications' })
  const box = await popover.boundingBox()
  if (!box || box.x < 0 || box.x + box.width > 375) throw new Error('mobile notification dropdown overflowed')
  await page.screenshot({ path: path.join(outputDir, '11-mobile-notification-dropdown.png') })
  await page.keyboard.press('Escape')
  await page.goto(`${baseUrl}/user/students`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /import students/i }).click()
  const importDialog = page.getByRole('dialog', { name: 'Import Students' })
  const importBox = await importDialog.boundingBox()
  if (!importBox || importBox.x < 0 || importBox.x + importBox.width > 375) throw new Error('mobile import dialog overflowed')
  await page.screenshot({ path: path.join(outputDir, '12-mobile-import-flow.png') })
})

await browser.close()

console.log(`phase10_12d_browser_checks=${results.length}`)
console.log(`phase10_12d_browser_failures=${results.filter(([, passed]) => !passed).length}`)
console.log(`page_errors=${pageErrors.length}`)
console.log(`native_dialogs=${nativeDialogs.length}`)
console.log(`console_errors=${consoleErrors.length}`)
console.log(`expected_console_errors=${expectedConsoleErrors.length}`)
for (const error of pageErrors) console.log(`page_error=${JSON.stringify(error)}`)
for (const error of nativeDialogs) console.log(`native_dialog=${JSON.stringify(error)}`)
for (const error of consoleErrors) console.log(`console_error=${JSON.stringify(error)}`)

if (results.some(([, passed]) => !passed) || pageErrors.length || nativeDialogs.length) process.exitCode = 1
