export const FULL_NAME_MIN_LENGTH = 2
export const FULL_NAME_MAX_LENGTH = 150
export const EMAIL_MAX_LENGTH = 180
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128

const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

export function normalizeEmail(value) {
  return value.trim().toLowerCase()
}

export function validateEmail(value) {
  const email = normalizeEmail(value)
  if (!email) return 'Email is required.'
  if (email.length > EMAIL_MAX_LENGTH) return `Email must be at most ${EMAIL_MAX_LENGTH} characters long.`
  if (!emailPattern.test(email)) return 'Enter a valid email address.'
  return ''
}

export function validatePassword(value) {
  if (!value || !value.trim()) return 'Password is required.'
  if (value.length < PASSWORD_MIN_LENGTH) return `Password must be at least ${PASSWORD_MIN_LENGTH} characters long.`
  if (value.length > PASSWORD_MAX_LENGTH) return `Password must be at most ${PASSWORD_MAX_LENGTH} characters long.`
  return ''
}

export function validateRegistrationForm(form) {
  const values = {
    fullName: form.fullName.trim(),
    email: normalizeEmail(form.email),
    password: form.password,
    requestedDepartmentId: Number(form.requestedDepartmentId),
  }
  const errors = {}

  if (!values.fullName) {
    errors.fullName = 'Full name is required.'
  } else if (values.fullName.length < FULL_NAME_MIN_LENGTH) {
    errors.fullName = `Full name must be at least ${FULL_NAME_MIN_LENGTH} characters long.`
  } else if (values.fullName.length > FULL_NAME_MAX_LENGTH) {
    errors.fullName = `Full name must be at most ${FULL_NAME_MAX_LENGTH} characters long.`
  }

  errors.email = validateEmail(values.email)
  if (!errors.email) delete errors.email

  errors.password = validatePassword(values.password)
  if (!errors.password) delete errors.password

  if (!Number.isInteger(values.requestedDepartmentId) || values.requestedDepartmentId <= 0) {
    errors.requestedDepartmentId = 'Please select a department.'
  }

  return { values, errors }
}
