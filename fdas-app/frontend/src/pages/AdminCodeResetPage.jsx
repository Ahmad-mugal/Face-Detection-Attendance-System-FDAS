import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api/authApi'
import { getApiError } from '../api/client'
import AuthRecoveryShell from '../components/AuthRecoveryShell'
import Icon from '../components/Icon'
import RecoveryPasswordFields from '../components/RecoveryPasswordFields'
import { normalizeEmail, validateEmail, validatePassword } from '../validation/authValidation'

const emptyForm = { email: '', recoveryCode: '', newPassword: '', confirmPassword: '' }

export default function AdminCodeResetPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(emptyForm)
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const setField = (name, value) => {
    setForm(current => ({ ...current, [name]: value }))
    setErrors(current => ({ ...current, [name]: '' }))
    setError('')
  }

  const submit = async event => {
    event.preventDefault()
    const nextErrors = {
      email: validateEmail(form.email),
      recoveryCode: form.recoveryCode.replace(/[^A-Za-z0-9]/g, '').length === 12 ? '' : 'Enter the complete 12-character recovery code.',
      newPassword: validatePassword(form.newPassword),
      confirmPassword: validatePassword(form.confirmPassword),
    }
    if (!nextErrors.confirmPassword && form.newPassword !== form.confirmPassword) nextErrors.confirmPassword = 'New password and confirmation do not match.'
    Object.keys(nextErrors).forEach(key => { if (!nextErrors[key]) delete nextErrors[key] })
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return
    setSubmitting(true)
    try {
      const result = await authApi.resetPasswordWithAdminCode({ ...form, email: normalizeEmail(form.email) })
      navigate('/login', { replace: true, state: { recoveryMessage: result.message } })
    } catch (err) {
      setError(getApiError(err, 'Unable to reset the password with this recovery code.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthRecoveryShell title="Administrator Recovery Code" description="Use the short-lived code provided directly by an administrator after your identity has been verified." icon="verified_user">
      {error && <div role="alert" className="mb-5 rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}
      <form onSubmit={submit} noValidate className="grid gap-5">
        <label className="grid gap-1" htmlFor="adminCodeEmail"><span className="fdas-label">Registered email</span><div className="fdas-auth-input-wrap"><span className="fdas-auth-leading-icon"><Icon name="person" size={19} /></span><input id="adminCodeEmail" type="email" autoComplete="email" maxLength="180" value={form.email} onChange={event => setField('email', event.target.value)} className="fdas-input fdas-auth-input-leading" aria-invalid={Boolean(errors.email)} /></div>{errors.email && <span className="text-xs font-semibold" style={{ color: '#93000a' }}>{errors.email}</span>}</label>
        <label className="grid gap-1" htmlFor="recoveryCode"><span className="fdas-label">Recovery code</span><div className="fdas-auth-input-wrap"><span className="fdas-auth-leading-icon"><Icon name="verified_user" size={19} /></span><input id="recoveryCode" type="text" autoComplete="one-time-code" maxLength="14" value={form.recoveryCode} onChange={event => setField('recoveryCode', event.target.value.toUpperCase())} placeholder="XXXX-XXXX-XXXX" className="fdas-input fdas-auth-input-leading font-mono uppercase tracking-wider" aria-invalid={Boolean(errors.recoveryCode)} /></div>{errors.recoveryCode && <span className="text-xs font-semibold" style={{ color: '#93000a' }}>{errors.recoveryCode}</span>}</label>
        <RecoveryPasswordFields form={form} setField={setField} errors={errors} />
        <button type="submit" disabled={submitting} className="fdas-button fdas-button-primary fdas-button-lg w-full">{submitting ? 'Resetting password…' : 'Reset Password'}</button>
      </form>
    </AuthRecoveryShell>
  )
}
