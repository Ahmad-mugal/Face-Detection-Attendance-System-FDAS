import { useEffect, useState } from 'react'
import StatsCard from '../../components/StatsCard'
import { adminUsersApi } from '../../api/adminUsersApi'
import { departmentsApi } from '../../api/departmentsApi'
import { getApiError } from '../../api/client'
import { ConfirmDialog, FormDialog } from '../../components/ui/Modal'
import Toast from '../../components/ui/Toast'

export default function AdminRequests() {
  const [requests, setRequests] = useState([])
  const [departments, setDepartments] = useState([])
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
      const [requestData, departmentData] = await Promise.all([
        adminUsersApi.listRequests(),
        departmentsApi.list(),
      ])
      setRequests(requestData)
      setDepartments(departmentData)
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
      <div>
        <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Access Control</p>
        <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Pending User Requests</h1>
      </div>

      <Toast message={message} tone={messageTone} onDismiss={() => setMessage('')} />
      {error && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Pending" value={requests.length} icon="pending_actions" />
        <StatsCard title="Departments" value={departments.length} icon="domain" iconColor="#D4A017" />
        <StatsCard title="Backend Source" value="Live" icon="cloud_done" iconColor="#065f46" />
      </div>

      <div className="rounded-xl fdas-card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center" style={{ color: '#887369' }}>Loading pending requests...</div>
        ) : requests.length === 0 ? (
          <div className="p-8 text-center" style={{ color: '#887369' }}>No pending user requests.</div>
        ) : (
          <div className="fdas-table-wrap">
            <table className="fdas-table">
              <thead className="text-xs uppercase" style={{ color: '#C4533A', backgroundColor: '#fff1eb' }}>
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
                      <span className="px-2.5 py-1 rounded-full text-xs font-bold" style={{ backgroundColor: '#FFF0E6', color: '#934619' }}>{request.status}</span>
                    </td>
                    <td className="p-4">
                      <div className="flex justify-end gap-2">
                        <button onClick={() => openApprove(request)} className="px-3 py-2 rounded-lg text-xs font-bold text-white" style={{ backgroundColor: '#D4A017' }}>Approve</button>
                        <button onClick={() => setModal({ type: 'reject', request })} className="px-3 py-2 rounded-lg text-xs font-bold border" style={{ borderColor: '#C4533A', color: '#C4533A' }}>Reject</button>
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
              <div className="grid gap-4 mt-5">
                <label>
                  <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Access Scope</span>
                  <select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} value={accessForm.accessScope} onChange={e => setAccessForm({ ...accessForm, accessScope: e.target.value })}>
                    <option value="Department">Department Access</option>
                    <option value="AllDepartments">All Departments</option>
                  </select>
                </label>
                {accessForm.accessScope === 'Department' && (
                  <label>
                    <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Department</span>
                    <select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} value={accessForm.assignedDepartmentId} onChange={e => setAccessForm({ ...accessForm, assignedDepartmentId: e.target.value })}>
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
