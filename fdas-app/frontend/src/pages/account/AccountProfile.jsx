import { useEffect, useMemo, useState } from 'react'
import { authApi } from '../../api/authApi'
import { getApiError } from '../../api/client'
import Icon from '../../components/Icon'
import Toast from '../../components/ui/Toast'
import { useAuth } from '../../context/useAuth'
import Badge from '../../components/ui/Badge'
import PageHeader from '../../components/ui/PageHeader'

function formatAccountDate(value) {
  if (!value) return 'Not available'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Not available' : date.toLocaleString()
}

function Detail({ label, value }) {
  return (
    <div className="rounded-xl border p-4" style={{ borderColor: '#f0dfd8', backgroundColor: '#fffdfb' }}>
      <dt className="text-xs font-bold uppercase tracking-wide" style={{ color: '#887369' }}>{label}</dt>
      <dd className="mt-1 font-bold break-words" style={{ color: '#4A2B0F' }}>{value || 'Not available'}</dd>
    </div>
  )
}

export default function AccountProfile() {
  const { currentUser, updateCurrentUser } = useAuth()
  const [fullName, setFullName] = useState(currentUser?.fullName || '')
  const [profileSaving, setProfileSaving] = useState(false)
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwords, setPasswords] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' })
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')

  useEffect(() => setFullName(currentUser?.fullName || ''), [currentUser?.fullName])

  const initials = useMemo(() => (currentUser?.fullName || 'FDAS User')
    .split(' ')
    .filter(Boolean)
    .map(part => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase(), [currentUser?.fullName])

  const saveProfile = async event => {
    event.preventDefault()
    setError('')
    setProfileSaving(true)
    try {
      const profile = await authApi.updateProfile({ fullName })
      updateCurrentUser(profile)
      setToast('Profile updated successfully.')
    } catch (err) {
      setError(getApiError(err, 'Unable to update your profile.'))
    } finally {
      setProfileSaving(false)
    }
  }

  const changePassword = async event => {
    event.preventDefault()
    setError('')
    if (passwords.newPassword !== passwords.confirmPassword) {
      setError('New password and confirmation do not match.')
      return
    }
    if (passwords.newPassword.length < 8) {
      setError('New password must be at least 8 characters long.')
      return
    }
    setPasswordSaving(true)
    try {
      await authApi.changePassword({ currentPassword: passwords.currentPassword, newPassword: passwords.newPassword })
      setPasswords({ currentPassword: '', newPassword: '', confirmPassword: '' })
      setToast('Password changed successfully.')
    } catch (err) {
      setError(getApiError(err, 'Unable to change your password.'))
    } finally {
      setPasswordSaving(false)
    }
  }

  const roleLabel = currentUser?.role === 'Admin' ? 'Administrator' : 'Operator'
  const scopeLabel = currentUser?.accessScope === 'AllDepartments' ? 'All departments' : 'Assigned department only'

  return (
    <section className="fdas-page space-y-6 animate-fade-in-up">
      <Toast message={toast} onDismiss={() => setToast('')} />
      <PageHeader eyebrow="Your Account" title="Account Profile" description="Review your access details, update your display name, and maintain account security." />
      <div className="p-5 sm:p-6 fdas-card border-t-4" style={{ borderTopColor: '#D4A017' }}>
        <div className="flex flex-col sm:flex-row sm:items-center gap-5">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-black text-white shadow-sm" style={{ backgroundColor: '#C4533A' }}>{initials}</div>
          <div className="min-w-0">
            <p className="text-lg font-bold break-words" style={{ color: '#4A2B0F' }}>{currentUser?.fullName}</p>
            <p className="mt-1 break-all" style={{ color: '#6f5b52' }}>{currentUser?.email}</p>
            <Badge tone="warning" className="mt-3">{roleLabel}</Badge>
          </div>
        </div>
      </div>

      {error && <div role="alert" className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
        <article className="p-5 sm:p-6 fdas-card">
          <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Account Information</h2>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-5">
            <Detail label="Name" value={currentUser?.fullName} />
            <Detail label="Email" value={currentUser?.email} />
            <Detail label="Role" value={roleLabel} />
            <Detail label="Department" value={currentUser?.assignedDepartmentName || (currentUser?.accessScope === 'AllDepartments' ? 'All departments' : 'Not assigned')} />
            <Detail label="Operational scope" value={scopeLabel} />
            <Detail label="Account status" value={currentUser?.status} />
          </dl>
          <div className="mt-6 pt-5 border-t" style={{ borderColor: '#f0dfd8' }}>
            <h3 className="font-black" style={{ color: '#4A2B0F' }}>System Information</h3>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
              <Detail label="Account created" value={formatAccountDate(currentUser?.createdAt)} />
              <Detail label="Last updated" value={formatAccountDate(currentUser?.updatedAt)} />
            </dl>
          </div>
        </article>

        <div className="space-y-6">
          <article className="p-5 sm:p-6 fdas-card">
            <div className="flex items-center gap-3"><Icon name="edit" size={21} style={{ color: '#C4533A' }} /><h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Edit Profile</h2></div>
            <p className="mt-2 text-sm" style={{ color: '#6f5b52' }}>You can update your display name. Role, email, department, and access scope remain administrator-controlled.</p>
            <form onSubmit={saveProfile} className="mt-5 space-y-4">
              <label className="block"><span className="fdas-label">Full name</span><input required minLength="2" maxLength="150" value={fullName} onChange={event => setFullName(event.target.value)} className="fdas-input mt-1" /></label>
              <label className="block"><span className="fdas-label">Email</span><input value={currentUser?.email || ''} disabled className="fdas-input mt-1" /></label>
              <button disabled={profileSaving || fullName.trim() === currentUser?.fullName} className="fdas-button fdas-button-primary w-full sm:w-auto">{profileSaving ? 'Saving…' : 'Save Changes'}</button>
            </form>
          </article>

          <article className="p-5 sm:p-6 fdas-card">
            <div className="flex items-center gap-3"><Icon name="lock" size={21} style={{ color: '#C4533A' }} /><h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Change Password</h2></div>
            <p className="mt-2 text-sm" style={{ color: '#6f5b52' }}>Your current password is required. FDAS keeps the existing PBKDF2 password policy.</p>
            <form onSubmit={changePassword} className="mt-5 grid gap-4">
              <label><span className="fdas-label">Current password</span><input required type="password" autoComplete="current-password" value={passwords.currentPassword} onChange={event => setPasswords({ ...passwords, currentPassword: event.target.value })} className="fdas-input mt-1" /></label>
              <label><span className="fdas-label">New password</span><input required minLength="8" maxLength="128" type="password" autoComplete="new-password" value={passwords.newPassword} onChange={event => setPasswords({ ...passwords, newPassword: event.target.value })} className="fdas-input mt-1" /></label>
              <label><span className="fdas-label">Confirm new password</span><input required minLength="8" maxLength="128" type="password" autoComplete="new-password" value={passwords.confirmPassword} onChange={event => setPasswords({ ...passwords, confirmPassword: event.target.value })} className="fdas-input mt-1" /></label>
              <button disabled={passwordSaving} className="fdas-button fdas-button-primary w-full sm:w-auto">{passwordSaving ? 'Changing…' : 'Change Password'}</button>
            </form>
          </article>
        </div>
      </div>
    </section>
  )
}
