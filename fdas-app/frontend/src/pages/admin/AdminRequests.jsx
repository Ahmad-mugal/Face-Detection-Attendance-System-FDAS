import { useEffect, useState } from 'react'
import StatsCard from '../../components/StatsCard'
import { adminUsersApi } from '../../api/adminUsersApi'
import { departmentsApi } from '../../api/departmentsApi'
import { getApiError } from '../../api/client'

export default function AdminRequests() {
  const [requests, setRequests] = useState([])
  const [departments, setDepartments] = useState([])
  const [modal, setModal] = useState(null)
  const [accessForm, setAccessForm] = useState({ accessScope: 'Department', assignedDepartmentId: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

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

  const submitModal = async () => {
    setSaving(true)
    setError('')
    try {
      if (modal.type === 'approve') {
        await adminUsersApi.approve(modal.request.userId, {
          accessScope: accessForm.accessScope,
          assignedDepartmentId: accessForm.accessScope === 'Department' ? Number(accessForm.assignedDepartmentId) : null,
        })
        setMessage('User approved successfully.')
      } else {
        await adminUsersApi.reject(modal.request.userId)
        setMessage('User request rejected.')
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

      {message && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#d1fae5', borderColor: '#86efac', color: '#065f46' }}>{message}</div>}
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

      {modal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40">
          <div className="w-full max-w-md rounded-xl p-5 fdas-card">
            <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>{modal.type === 'approve' ? 'Approve User Request' : 'Reject User Request'}</h2>
            <p className="text-sm mt-1" style={{ color: '#55433b' }}>{modal.request.fullName} - {modal.request.email}</p>
            {modal.type === 'approve' ? (
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
            ) : (
              <p className="mt-5 rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>This will reject the request in the backend.</p>
            )}
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg border font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Cancel</button>
              <button disabled={saving} onClick={submitModal} className="px-4 py-2 rounded-lg font-bold text-white disabled:opacity-60" style={{ backgroundColor: modal.type === 'approve' ? '#D4A017' : '#C4533A' }}>
                {saving ? 'Saving...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
