import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/authApi'
import { getApiError } from '../api/client'
import AuthRecoveryShell from '../components/AuthRecoveryShell'
import Icon from '../components/Icon'
import { normalizeEmail, validateEmail } from '../validation/authValidation'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async event => {
    event.preventDefault()
    const validationError = validateEmail(email)
    setError(validationError)
    setMessage('')
    if (validationError) return
    setSubmitting(true)
    try {
      const result = await authApi.forgotPassword({ email: normalizeEmail(email) })
      setMessage(result.message)
    } catch (err) {
      setError(getApiError(err, 'Unable to prepare password recovery. Please try again later.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthRecoveryShell title="Forgot Password" description="Enter your registered email address. If password recovery is available for that account, you will receive instructions." icon="mail_lock">
      {message && <div role="status" className="mb-5 rounded-xl border px-4 py-3 text-sm font-semibold leading-6" style={{ backgroundColor: '#d1fae5', borderColor: '#86efac', color: '#065f46' }}>{message}</div>}
      {error && <div role="alert" className="mb-5 rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}
      <form onSubmit={submit} noValidate className="grid gap-5">
        <label className="grid gap-1" htmlFor="recoveryEmail">
          <span className="fdas-label">Email address</span>
          <div className="fdas-auth-input-wrap">
            <span className="fdas-auth-leading-icon"><Icon name="forward_to_inbox" size={19} /></span>
            <input id="recoveryEmail" type="email" autoComplete="email" maxLength="180" value={email} onChange={event => { setEmail(event.target.value); setError(''); setMessage('') }} className="fdas-input fdas-auth-input-leading" aria-invalid={Boolean(error)} />
          </div>
        </label>
        <button type="submit" disabled={submitting} className="fdas-button fdas-button-primary fdas-button-lg w-full">{submitting ? 'Preparing instructions…' : 'Send Reset Instructions'}</button>
      </form>
      <div className="mt-5 rounded-xl border p-4 text-center text-sm" style={{ borderColor: '#eadbd4', backgroundColor: '#fffdfb', color: '#55433b' }}>
        Email unavailable?{' '}
        <Link to="/reset-password/admin-code" className="font-bold underline underline-offset-2" style={{ color: '#934619' }}>Have an administrator recovery code?</Link>
      </div>
    </AuthRecoveryShell>
  )
}
