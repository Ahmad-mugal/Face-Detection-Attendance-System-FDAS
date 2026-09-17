import { useEffect, useState } from 'react'
import StatsCard from '../../components/StatsCard'
import { adminUsersApi } from '../../api/adminUsersApi'
import { departmentsApi } from '../../api/departmentsApi'
import { getApiError } from '../../api/client'
import { ConfirmDialog, FormDialog } from '../../components/ui/Modal'
import Toast from '../../components/ui/Toast'
import Badge from '../../components/ui/Badge'
import PageHeader from '../../components/ui/PageHeader'
import { EmptyState, LoadingState } from '../../components/ui/AsyncState'

export default function AdminRequests() {
  const [requests, setRequests] = useState([])
  const [departments, setDepartments] = useState([])
  const [emailCapability, setEmailCapability] = useState(null)
  const [modal, setModal] = useState(null)
  const [accessForm, setAccessForm] = useState({ accessScope: 'Department', assignedDepartmentId: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [messageTone, setMessageTone] = useState('success')

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [requestData, departmentData, emailStatus] = await Promise.all([
        adminUsersApi.listRequests(),
        departmentsApi.list(),
        adminUsersApi.emailStatus(),
      ])
      setRequests(requestData)
      setDepartments(departmentData)
      setEmailCapability(emailStatus)
    } catch (err) {
      setError(getApiError(err, 'Unable to load pending requests.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const openApprove = request => {
    setAccessForm({
      accessScope: 'Department',
      assignedDepartmentId: String(request.assignedDepartmentId || departments[0]?.departmentId || ''),
    })
    setModal({ type: 'approve', request })
  }

  const submitModal = async event => {
    event?.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (modal.type === 'approve') {
        const result = await adminUsersApi.approve(modal.request.userId, {
          accessScope: accessForm.accessScope,
          assignedDepartmentId: accessForm.accessScope === 'Department' ? Number(accessForm.assignedDepartmentId) : null,
        })
        if (result.emailNotificationSent) {
          setMessage('Operator approved. Approval email sent successfully.')
          setMessageTone('success')
        } else if (result.emailNotificationMessage?.includes('not configured')) {
          setMessage('Operator approved. Notification email unavailable because SMTP is not configured.')
          setMessageTone('info')
        } else {
          setMessage('Operator approved, but the notification email could not be sent.')
          setMessageTone('info')
        }
      } else {
        await adminUsersApi.reject(modal.request.userId)
        setMessage('User request rejected.')
        setMessageTone('success')
      }
      setModal(null)
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to update request.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <PageHeader eyebrow="Access Control" title="Pending User Requests" description="Review operator registrations and assign the correct department access before approval." />

      <Toast message={message} tone={messageTone} onDismiss={() => setMessage('')} />
      {error && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Pending" value={requests.length} icon="pending_actions" />
        <StatsCard title="Departments" value={departments.length} icon="domain" iconColor="#D4A017" />
        <StatsCard title="Approval Email" value={emailCapability?.configured ? 'Ready' : 'Setup Needed'} icon={emailCapability?.configured ? 'mark_email_read' : 'mail_lock'} iconColor={emailCapability?.configured ? '#065f46' : '#934619'} />
      </div>

      {emailCapability && (
        <div className="rounded-xl border px-4 py-3 text-sm" style={{ borderColor: '#dbc1b7', backgroundColor: '#fff8f6', color: '#55433b' }}>
          <span className="font-bold">SMTP status:</span> {emailCapability.message}
        </div>
      )}

      <div className="fdas-card overflow-hidden">
        {loading ? (
          <LoadingState label="Loading pending requests…" />
        ) : requests.length === 0 ? (
          <EmptyState title="No pending user requests" description="New operator registrations will appear here for review." icon="pending_actions" />
        ) : (
          <div className="fdas-table-wrap">
            <table className="fdas-table">
              <thead>
                <tr>
                  <th className="p-4">Name</th>
                  <th className="p-4">Email</th>
                  <th className="p-4">Requested Department</th>
                  <th className="p-4">Status</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {requests.map(request => (
                  <tr key={request.userId} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                    <td className="p-4 font-bold" style={{ color: '#4A2B0F' }}>{request.fullName}</td>
                    <td className="p-4 text-sm" style={{ color: '#55433b' }}>{request.email}</td>
                    <td className="p-4">{request.assignedDepartment || 'Not assigned'}</td>
                    <td className="p-4">
                      <Badge>{request.status}</Badge>
                    </td>
                    <td className="p-4">
                      <div className="flex justify-end gap-2">
                        <button onClick={() => openApprove(request)} className="fdas-button fdas-button-warning fdas-button-sm">Approve</button>
                        <button onClick={() => setModal({ type: 'reject', request })} className="fdas-button fdas-button-outline fdas-button-sm">Reject</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <FormDialog open={modal?.type === 'approve'} onClose={() => setModal(null)} onSubmit={submitModal} title="Approve User Request" description={modal?.request ? `${modal.request.fullName} — ${modal.request.email}` : ''} submitLabel="Approve User" busy={saving}>
              <div className="grid gap-4">
                <label>
                  <span className="fdas-label">Access Scope</span>
                  <select className="fdas-input mt-1" value={accessForm.accessScope} onChange={e => setAccessForm({ ...accessForm, accessScope: e.target.value })}>
                    <option value="Department">Department Access</option>
                    <option value="AllDepartments">All Departments</option>
                  </select>
                </label>
                {accessForm.accessScope === 'Department' && (
                  <label>
                    <span className="fdas-label">Department</span>
                    <select className="fdas-input mt-1" value={accessForm.assignedDepartmentId} onChange={e => setAccessForm({ ...accessForm, assignedDepartmentId: e.target.value })}>
                      {departments.map(item => <option key={item.departmentId} value={item.departmentId}>{item.departmentName}</option>)}
                    </select>
                  </label>
                )}
              </div>
      </FormDialog>

      <ConfirmDialog open={modal?.type === 'reject'} onClose={() => setModal(null)} onConfirm={submitModal} title="Reject User Request?" description={modal?.request ? `${modal.request.fullName} — ${modal.request.email}` : ''} confirmLabel="Reject Request" destructive busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>The pending request will be rejected and the user will not receive application access.</p>
      </ConfirmDialog>
    </section>
  )
}
