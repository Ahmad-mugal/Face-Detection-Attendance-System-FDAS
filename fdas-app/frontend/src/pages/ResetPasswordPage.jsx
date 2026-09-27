import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '../api/authApi'
import { getApiError } from '../api/client'
import AuthRecoveryShell from '../components/AuthRecoveryShell'
import RecoveryPasswordFields from '../components/RecoveryPasswordFields'
import { validatePassword } from '../validation/authValidation'

const emptyForm = { newPassword: '', confirmPassword: '' }

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') || ''
  const [form, setForm] = useState(emptyForm)
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(token ? '' : 'This password reset link is invalid or incomplete.')
  const [submitting, setSubmitting] = useState(false)

  const setField = (name, value) => {
    setForm(current => ({ ...current, [name]: value }))
    setErrors(current => ({ ...current, [name]: '' }))
    setError('')
  }

  const submit = async event => {
    event.preventDefault()
    const nextErrors = {
      newPassword: validatePassword(form.newPassword),
      confirmPassword: validatePassword(form.confirmPassword),
    }
    if (!nextErrors.confirmPassword && form.newPassword !== form.confirmPassword) nextErrors.confirmPassword = 'New password and confirmation do not match.'
    Object.keys(nextErrors).forEach(key => { if (!nextErrors[key]) delete nextErrors[key] })
    setErrors(nextErrors)
    if (!token || Object.keys(nextErrors).length) return
    setSubmitting(true)
    try {
      const result = await authApi.resetPassword({ token, ...form })
      navigate('/login', { replace: true, state: { recoveryMessage: result.message } })
    } catch (err) {
      setError(getApiError(err, 'Unable to reset the password.'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthRecoveryShell title="Reset Password" description="Choose a new FDAS password. This short-lived link can be used only once.">
      {error && <div role="alert" className="mb-5 rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}
      <form onSubmit={submit} noValidate className="grid gap-5">
        <RecoveryPasswordFields form={form} setField={setField} errors={errors} />
        <button type="submit" disabled={submitting || !token} className="fdas-button fdas-button-primary fdas-button-lg w-full">{submitting ? 'Resetting password…' : 'Reset Password'}</button>
      </form>
    </AuthRecoveryShell>
  )
}
