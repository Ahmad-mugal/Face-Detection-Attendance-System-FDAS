import { useEffect, useState } from 'react'
import CSVExportButton from '../../components/CSVExportButton'
import { adminUsersApi } from '../../api/adminUsersApi'
import { departmentsApi } from '../../api/departmentsApi'
import { getApiError } from '../../api/client'
import { ConfirmDialog, FormDialog, Modal } from '../../components/ui/Modal'
import Toast from '../../components/ui/Toast'
import Icon from '../../components/Icon'
import Badge from '../../components/ui/Badge'
import PageHeader from '../../components/ui/PageHeader'
import { EmptyState, LoadingState } from '../../components/ui/AsyncState'

export default function AdminUsers() {
  const [users, setUsers] = useState([])
  const [departments, setDepartments] = useState([])
  const [modalUser, setModalUser] = useState(null)
  const [actionDialog, setActionDialog] = useState(null)
  const [accessForm, setAccessForm] = useState({ accessScope: 'Department', assignedDepartmentId: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [messageTone, setMessageTone] = useState('success')
  const [recoveryResult, setRecoveryResult] = useState(null)

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [userData, departmentData] = await Promise.all([
        adminUsersApi.listUsers(),
        departmentsApi.list(),
      ])
      setUsers(userData)
      setDepartments(departmentData)
    } catch (err) {
      setError(getApiError(err, 'Unable to load users.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const openAccessModal = user => {
    setAccessForm({
      accessScope: user.accessScope,
      assignedDepartmentId: String(user.assignedDepartmentId || departments[0]?.departmentId || ''),
    })
    setModalUser(user)
  }

  const saveAccess = async event => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await adminUsersApi.updateAccess(modalUser.userId, {
        accessScope: accessForm.accessScope,
        assignedDepartmentId: accessForm.accessScope === 'Department' ? Number(accessForm.assignedDepartmentId) : null,
      })
      setMessage('User access updated.')
      setMessageTone('success')
      setModalUser(null)
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to update access.'))
    } finally {
      setSaving(false)
    }
  }

  const changeStatus = async user => {
    setSaving(true)
    setError('')
    try {
      if (user.status === 'Disabled') {
        await adminUsersApi.enable(user.userId)
        setMessage('User enabled.')
      } else {
        await adminUsersApi.disable(user.userId)
        setMessage('User disabled.')
      }
      setMessageTone('success')
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to update user status.'))
    } finally {
      setSaving(false)
      setActionDialog(null)
    }
  }

  const deleteUser = async user => {
    setSaving(true)
    setError('')
    try {
      const result = await adminUsersApi.delete(user.userId)
      setMessage(result.message)
      setMessageTone('success')
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to delete the user.'))
    } finally {
      setSaving(false)
      setActionDialog(null)
    }
  }

  const resendApprovalEmail = async user => {
    setSaving(true)
    setError('')
    try {
      const result = await adminUsersApi.resendApprovalEmail(user.userId)
      if (result.emailNotificationSent) {
        setMessage('Approval email sent successfully.')
        setMessageTone('success')
      } else if (result.emailNotificationMessage?.includes('not configured')) {
        setMessage('Approval email unavailable because SMTP is not configured.')
        setMessageTone('info')
      } else {
        setMessage('Approval email could not be sent.')
        setMessageTone('info')
      }
    } catch (err) {
      setError(getApiError(err, 'Unable to resend the approval email.'))
    } finally {
      setSaving(false)
      setActionDialog(null)
    }
  }

  const generateRecoveryCode = async user => {
    setSaving(true)
    setError('')
    try {
      const result = await adminUsersApi.generatePasswordRecoveryCode(user.userId)
      setRecoveryResult({ ...result, user })
      setMessage('One-time password recovery code generated.')
      setMessageTone('success')
    } catch (err) {
      setError(getApiError(err, 'Unable to generate a password recovery code.'))
    } finally {
      setSaving(false)
      setActionDialog(null)
    }
  }

  const copyRecoveryCode = async () => {
    if (!recoveryResult?.recoveryCode) return
    try {
      await navigator.clipboard.writeText(recoveryResult.recoveryCode)
      setMessage('Recovery code copied. Share it only with the verified Operator.')
      setMessageTone('info')
    } catch {
      setMessage('Copy was blocked by the browser. Select the code and copy it manually.')
      setMessageTone('warning')
    }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <PageHeader
        eyebrow="User Management"
        title="Manage Users"
        description="Review account status, department assignment, and access scope for FDAS administrators and operators."
        actions={<CSVExportButton data={users} filename="fdas_users.csv" />}
      />

      <Toast message={message} tone={messageTone} onDismiss={() => setMessage('')} />
      {error && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="fdas-card overflow-hidden">
        {loading ? (
          <LoadingState label="Loading users…" />
        ) : users.length === 0 ? (
          <EmptyState title="No users found" description="Approved accounts will appear here once they are available." icon="manage_accounts" />
        ) : (
          <div className="fdas-table-wrap">
            <table className="fdas-table fdas-users-table table-fixed">
              <colgroup>
                <col className="w-[15%]" />
                <col className="w-[18%]" />
                <col className="w-[7%]" />
                <col className="w-[13%]" />
                <col className="w-[12%]" />
                <col className="w-[10%]" />
                <col className="w-[25%]" />
              </colgroup>
              <thead>
                <tr>
                  <th className="p-4">Name</th>
                  <th className="p-4">Email</th>
                  <th className="p-4">Role</th>
                  <th className="p-4">Assigned Department</th>
                  <th className="p-4">Access Scope</th>
                  <th className="p-4 fdas-users-status-cell">Status</th>
                  <th className="p-4 text-right fdas-users-actions-cell">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user.userId}>
                    <td className="font-bold" style={{ color: '#4A2B0F' }}><span className="line-clamp-2">{user.fullName}</span></td>
                    <td className="text-sm" style={{ color: '#55433b' }}><span className="block truncate" title={user.email}>{user.email}</span></td>
                    <td>{user.role}</td>
                    <td><span className="line-clamp-2">{user.assignedDepartment || 'All Departments'}</span></td>
                    <td><span className="line-clamp-2">{user.accessScope === 'AllDepartments' ? 'All Departments' : 'Department Only'}</span></td>
                    <td className="fdas-users-status-cell">
                      <Badge>{user.status}</Badge>
                    </td>
                    <td className="fdas-users-actions-cell">
                      <div className="fdas-table-actions fdas-user-actions">
                        <button onClick={() => openAccessModal(user)} className="fdas-button fdas-button-primary fdas-button-sm">Change Access</button>
                        <button onClick={() => setActionDialog({ type: 'status', user })} className={`fdas-button fdas-button-sm ${user.status === 'Disabled' ? 'fdas-button-secondary' : 'fdas-button-outline'}`}>
                          {user.status === 'Disabled' ? 'Enable' : 'Disable'}
                        </button>
                        {user.role === 'User' && user.status === 'Approved' && (
                          <button
                            onClick={() => setActionDialog({ type: 'resend', user })}
                            className="fdas-icon-button fdas-icon-button-sm"
                            title="Resend approval email"
                            aria-label={`Resend approval email to ${user.fullName}`}
                          >
                            <Icon name="forward_to_inbox" size={17} />
                          </button>
                        )}
                        {user.role === 'User' && (
                          <button
                            type="button"
                            onClick={() => setActionDialog({ type: 'recovery', user })}
                            disabled={!['Approved', 'Disabled'].includes(user.status)}
                            className="fdas-icon-button fdas-icon-button-sm"
                            title={['Approved', 'Disabled'].includes(user.status) ? 'Generate password recovery code' : 'Recovery requires an approved or disabled account'}
                            aria-label={`Generate password recovery code for ${user.fullName}`}
                          >
                            <Icon name="verified_user" size={17} />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => setActionDialog({ type: 'delete', user })}
                          disabled={user.role === 'Admin'}
                          className="fdas-icon-button fdas-icon-button-sm"
                          style={{ color: '#ba1a1a' }}
                          title={user.role === 'Admin' ? 'Administrator accounts are protected' : 'Delete user'}
                          aria-label={user.role === 'Admin' ? `${user.fullName} is a protected administrator` : `Delete ${user.fullName}`}
                        >
                          <Icon name="delete" size={17} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <FormDialog open={Boolean(modalUser)} onClose={() => setModalUser(null)} onSubmit={saveAccess} title="Change User Access" description={modalUser?.fullName} submitLabel="Save Access" busy={saving}>
            <div className="grid gap-4">
              <label>
                <span className="fdas-label">Access Scope</span>
                <select className="fdas-input mt-1" value={accessForm.accessScope} onChange={e => setAccessForm({ ...accessForm, accessScope: e.target.value })}>
                  <option value="Department">Department Only</option>
                  <option value="AllDepartments">All Departments</option>
                </select>
              </label>
              {accessForm.accessScope === 'Department' && (
                <label>
                  <span className="fdas-label">Assigned Department</span>
                  <select className="fdas-input mt-1" value={accessForm.assignedDepartmentId} onChange={e => setAccessForm({ ...accessForm, assignedDepartmentId: e.target.value })}>
                    {departments.map(item => <option key={item.departmentId} value={item.departmentId}>{item.departmentName}</option>)}
                  </select>
                </label>
              )}
            </div>
      </FormDialog>

      <ConfirmDialog open={actionDialog?.type === 'status'} onClose={() => setActionDialog(null)} onConfirm={() => changeStatus(actionDialog.user)} title={actionDialog?.user?.status === 'Disabled' ? 'Activate User?' : 'Deactivate User?'} description={actionDialog?.user?.fullName} confirmLabel={actionDialog?.user?.status === 'Disabled' ? 'Activate' : 'Deactivate'} destructive={actionDialog?.user?.status !== 'Disabled'} busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>{actionDialog?.user?.status === 'Disabled' ? 'This user will regain access according to their assigned scope.' : 'This user will no longer be able to sign in until reactivated.'}</p>
      </ConfirmDialog>

      <ConfirmDialog open={actionDialog?.type === 'resend'} onClose={() => setActionDialog(null)} onConfirm={() => resendApprovalEmail(actionDialog.user)} title="Resend Approval Email?" description={actionDialog?.user ? `${actionDialog.user.fullName} — ${actionDialog.user.email}` : ''} confirmLabel="Send Email" busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>This sends another approval notice to the operator's registered email. It does not change account access or include a password.</p>
      </ConfirmDialog>

      <ConfirmDialog open={actionDialog?.type === 'delete'} onClose={() => setActionDialog(null)} onConfirm={() => deleteUser(actionDialog.user)} title="Delete User?" description={actionDialog?.user ? `${actionDialog.user.fullName} — ${actionDialog.user.email}` : ''} confirmLabel="Delete User" destructive busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#ffdad6', color: '#93000a' }}>Are you sure you want to permanently delete this user? This action cannot be undone. Accounts with historical dependencies will remain unchanged and should be disabled instead.</p>
      </ConfirmDialog>

      <ConfirmDialog open={actionDialog?.type === 'recovery'} onClose={() => setActionDialog(null)} onConfirm={() => generateRecoveryCode(actionDialog.user)} title="Generate Password Recovery Code?" description={actionDialog?.user ? `${actionDialog.user.fullName} — ${actionDialog.user.email}` : ''} confirmLabel="Generate Code" busy={saving}>
        <div className="space-y-3 rounded-xl border p-4 text-sm" style={{ backgroundColor: '#FFF0E6', borderColor: '#ebcf7b', color: '#55433b' }}>
          <p className="font-bold" style={{ color: '#4A2B0F' }}>Verify the Operator's identity before continuing.</p>
          <p>The generated code expires in 10 minutes, works once, and is shown only once. Give it directly to the verified Operator.</p>
          <p>The Operator chooses their own final password; administrators never see or set it.</p>
        </div>
      </ConfirmDialog>

      <Modal
        open={Boolean(recoveryResult)}
        onClose={() => setRecoveryResult(null)}
        title="One-Time Recovery Code"
        description={recoveryResult ? `${recoveryResult.user.fullName} — ${recoveryResult.user.email}` : ''}
        size="md"
        footer={<button type="button" onClick={() => setRecoveryResult(null)} className="fdas-button fdas-button-primary">Done</button>}
      >
        <div className="space-y-4">
          <div className="rounded-xl border p-4" style={{ backgroundColor: '#fffdfb', borderColor: '#dbc1b7' }}>
            <label htmlFor="generatedRecoveryCode" className="fdas-label">Recovery code</label>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <input id="generatedRecoveryCode" readOnly value={recoveryResult?.recoveryCode || ''} className="fdas-input flex-1 text-center font-mono text-lg font-black tracking-widest" />
              <button type="button" onClick={copyRecoveryCode} className="fdas-button fdas-button-secondary">Copy Code</button>
            </div>
          </div>
          <p className="text-sm leading-6" style={{ color: '#55433b' }}>This code expires at {recoveryResult ? new Date(recoveryResult.expiresAt).toLocaleTimeString() : ''}. It cannot be viewed again after this dialog closes. Do not email it or store it in notes.</p>
        </div>
      </Modal>
    </section>
  )
}
