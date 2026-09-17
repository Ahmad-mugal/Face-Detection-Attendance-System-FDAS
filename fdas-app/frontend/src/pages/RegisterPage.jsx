import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/authApi'
import { getApiError } from '../api/client'
import Icon from '../components/Icon'
import { PASSWORD_MIN_LENGTH, validateRegistrationForm } from '../validation/authValidation'

const emptyForm = { fullName: '', email: '', password: '', requestedDepartmentId: '' }

export default function RegisterPage() {
  const [form, setForm] = useState(emptyForm)
  const [departments, setDepartments] = useState([])
  const [fieldErrors, setFieldErrors] = useState({})
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loadingDepartments, setLoadingDepartments] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let active = true
    authApi.registrationDepartments()
      .then(items => {
        if (!active) return
        setDepartments(items)
        if (items.length === 1) {
          setForm(current => ({ ...current, requestedDepartmentId: String(items[0].departmentId) }))
        }
      })
      .catch(err => {
        if (active) setError(getApiError(err, 'Unable to load departments.'))
      })
      .finally(() => {
        if (active) setLoadingDepartments(false)
      })
    return () => { active = false }
  }, [])

  const updateField = (name, value) => {
    setForm(current => ({ ...current, [name]: value }))
    setFieldErrors(current => ({ ...current, [name]: '' }))
    setError('')
    setMessage('')
  }

  const handleSubmit = async event => {
    event.preventDefault()
    if (submitting) return

    const { values, errors } = validateRegistrationForm(form)
    setFieldErrors(errors)
    setError('')
    setMessage('')
    if (Object.keys(errors).length > 0) return

    setSubmitting(true)
    try {
      await authApi.registerRequest(values)
      setForm(emptyForm)
      setMessage('Registration request submitted. An administrator must approve your account before you can sign in.')
    } catch (err) {
      setError(getApiError(err, 'Unable to submit registration request.'))
    } finally {
      setSubmitting(false)
    }
  }

  const fieldClass = 'fdas-input'
  const fieldStyle = { borderColor: '#dbc1b7', color: '#4A2B0F', backgroundColor: '#ffffff' }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-6" style={{ backgroundColor: '#FAF4EC' }}>
      <main className="w-full max-w-2xl rounded-2xl overflow-hidden border-t-4" style={{ backgroundColor: '#fff8f6', borderColor: '#D4A017', boxShadow: '0 8px 40px rgba(232,146,74,0.2)' }}>
        <section className="p-6 sm:p-8 md:p-10">
          <header className="text-center mb-7">
            <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full" style={{ backgroundColor: '#FFF0E6', color: '#C4533A' }}>
              <Icon name="person" size={30} />
            </div>
            <p className="text-xs font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>FDAS Access</p>
            <h1 className="text-3xl font-black mt-1" style={{ color: '#4A2B0F' }}>Request an Account</h1>
            <p className="text-sm mt-2" style={{ color: '#55433b' }}>Submit your details for administrator approval.</p>
          </header>

          {message && <div role="status" className="mb-5 rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#d1fae5', borderColor: '#86efac', color: '#065f46' }}>{message}</div>}
          {error && <div role="alert" className="mb-5 rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

          <form onSubmit={handleSubmit} noValidate className="grid gap-5">
            <label className="grid gap-1">
              <span className="fdas-label">Full Name</span>
              <input
                type="text"
                autoComplete="name"
                maxLength={150}
                value={form.fullName}
                onChange={event => updateField('fullName', event.target.value)}
                className={fieldClass}
                style={fieldStyle}
                aria-invalid={Boolean(fieldErrors.fullName)}
              />
              {fieldErrors.fullName && <span className="text-xs font-semibold" style={{ color: '#93000a' }}>{fieldErrors.fullName}</span>}
            </label>

            <label className="grid gap-1">
              <span className="fdas-label">Email</span>
              <input
                type="email"
                autoComplete="email"
                maxLength={180}
                value={form.email}
                onChange={event => updateField('email', event.target.value)}
                placeholder="name@fdas.local"
                className={fieldClass}
                style={fieldStyle}
                aria-invalid={Boolean(fieldErrors.email)}
              />
              {fieldErrors.email && <span className="text-xs font-semibold" style={{ color: '#93000a' }}>{fieldErrors.email}</span>}
            </label>

            <label className="grid gap-1">
              <span className="fdas-label">Password</span>
              <input
                type="password"
                autoComplete="new-password"
                maxLength={128}
                value={form.password}
                onChange={event => updateField('password', event.target.value)}
                className={fieldClass}
                style={fieldStyle}
                aria-invalid={Boolean(fieldErrors.password)}
              />
              <span className="text-xs" style={{ color: '#887369' }}>Use at least {PASSWORD_MIN_LENGTH} characters. Spaces-only passwords are not accepted.</span>
              {fieldErrors.password && <span className="text-xs font-semibold" style={{ color: '#93000a' }}>{fieldErrors.password}</span>}
            </label>

            <label className="grid gap-1">
              <span className="fdas-label">Requested Department</span>
              <select
                value={form.requestedDepartmentId}
                onChange={event => updateField('requestedDepartmentId', event.target.value)}
                disabled={loadingDepartments}
                className={`${fieldClass} disabled:opacity-60`}
                style={fieldStyle}
                aria-invalid={Boolean(fieldErrors.requestedDepartmentId)}
              >
                <option value="">{loadingDepartments ? 'Loading departments...' : 'Select a department'}</option>
                {departments.map(department => (
                  <option key={department.departmentId} value={department.departmentId}>{department.departmentName}</option>
                ))}
              </select>
              {fieldErrors.requestedDepartmentId && <span className="text-xs font-semibold" style={{ color: '#93000a' }}>{fieldErrors.requestedDepartmentId}</span>}
            </label>

            <button
              type="submit"
              disabled={submitting || loadingDepartments}
              className="fdas-button fdas-button-primary fdas-button-lg w-full"
              style={{ background: submitting ? '#887369' : 'linear-gradient(135deg, #C4533A 0%, #934619 100%)' }}
            >
              {submitting ? 'Submitting request...' : 'Submit Registration Request'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm" style={{ color: '#55433b' }}>
            Already have an account?{' '}
            <Link to="/login" className="font-bold underline underline-offset-2" style={{ color: '#934619' }}>Sign in</Link>
          </p>
        </section>
      </main>
    </div>
  )
}
