import { useEffect, useState } from 'react'
import CSVExportButton from '../../components/CSVExportButton'
import { adminUsersApi } from '../../api/adminUsersApi'
import { departmentsApi } from '../../api/departmentsApi'
import { getApiError } from '../../api/client'
import { ConfirmDialog, FormDialog } from '../../components/ui/Modal'
import Toast from '../../components/ui/Toast'

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
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to update user status.'))
    } finally {
      setSaving(false)
      setActionDialog(null)
    }
  }

  const grantAll = async user => {
    setSaving(true)
    setError('')
    try {
      await adminUsersApi.updateAccess(user.userId, { accessScope: 'AllDepartments', assignedDepartmentId: null })
      setMessage('All departments access granted.')
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to grant access.'))
    } finally {
      setSaving(false)
      setActionDialog(null)
    }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Administration</p>
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Manage Users</h1>
        </div>
        <CSVExportButton data={users} filename="fdas_users.csv" />
      </div>

      <Toast message={message} onDismiss={() => setMessage('')} />
      {error && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="rounded-xl fdas-card overflow-hidden">
        {loading ? (
          <div className="p-8 text-center" style={{ color: '#887369' }}>Loading users...</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center" style={{ color: '#887369' }}>No users found.</div>
        ) : (
          <div className="fdas-table-wrap">
            <table className="fdas-table">
              <thead className="text-xs uppercase" style={{ color: '#C4533A', backgroundColor: '#fff1eb' }}>
                <tr>
                  <th className="p-4">Name</th>
                  <th className="p-4">Email</th>
                  <th className="p-4">Role</th>
                  <th className="p-4">Assigned Department</th>
                  <th className="p-4">Access Scope</th>
                  <th className="p-4">Status</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user.userId} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                    <td className="p-4 font-bold" style={{ color: '#4A2B0F' }}>{user.fullName}</td>
                    <td className="p-4 text-sm" style={{ color: '#55433b' }}>{user.email}</td>
                    <td className="p-4">{user.role}</td>
                    <td className="p-4">{user.assignedDepartment || 'All Departments'}</td>
                    <td className="p-4">{user.accessScope === 'AllDepartments' ? 'All Departments' : 'Department Only'}</td>
                    <td className="p-4">
                      <span className="px-2 py-1 rounded-full text-xs font-bold" style={{ backgroundColor: user.status === 'Approved' ? '#d1fae5' : '#ffdad6', color: user.status === 'Approved' ? '#065f46' : '#93000a' }}>{user.status}</span>
                    </td>
                    <td className="p-4">
                      <div className="flex justify-end gap-2 flex-wrap">
                        <button onClick={() => openAccessModal(user)} className="px-3 py-2 rounded-lg text-xs font-bold border" style={{ borderColor: '#D4A017', color: '#715300' }}>Change Access</button>
                        <button onClick={() => setActionDialog({ type: 'grant', user })} className="px-3 py-2 rounded-lg text-xs font-bold text-white" style={{ backgroundColor: '#D4A017' }}>Grant All</button>
                        <button onClick={() => setActionDialog({ type: 'status', user })} className="px-3 py-2 rounded-lg text-xs font-bold border" style={{ borderColor: user.status === 'Disabled' ? '#065f46' : '#C4533A', color: user.status === 'Disabled' ? '#065f46' : '#C4533A' }}>
                          {user.status === 'Disabled' ? 'Enable' : 'Disable'}
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
            <div className="grid gap-4 mt-5">
              <label>
                <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Access Scope</span>
                <select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} value={accessForm.accessScope} onChange={e => setAccessForm({ ...accessForm, accessScope: e.target.value })}>
                  <option value="Department">Department Only</option>
                  <option value="AllDepartments">All Departments</option>
                </select>
              </label>
              {accessForm.accessScope === 'Department' && (
                <label>
                  <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Assigned Department</span>
                  <select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} value={accessForm.assignedDepartmentId} onChange={e => setAccessForm({ ...accessForm, assignedDepartmentId: e.target.value })}>
                    {departments.map(item => <option key={item.departmentId} value={item.departmentId}>{item.departmentName}</option>)}
                  </select>
                </label>
              )}
            </div>
      </FormDialog>

      <ConfirmDialog open={actionDialog?.type === 'status'} onClose={() => setActionDialog(null)} onConfirm={() => changeStatus(actionDialog.user)} title={actionDialog?.user?.status === 'Disabled' ? 'Activate User?' : 'Deactivate User?'} description={actionDialog?.user?.fullName} confirmLabel={actionDialog?.user?.status === 'Disabled' ? 'Activate' : 'Deactivate'} destructive={actionDialog?.user?.status !== 'Disabled'} busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>{actionDialog?.user?.status === 'Disabled' ? 'This user will regain access according to their assigned scope.' : 'This user will no longer be able to sign in until reactivated.'}</p>
      </ConfirmDialog>

      <ConfirmDialog open={actionDialog?.type === 'grant'} onClose={() => setActionDialog(null)} onConfirm={() => grantAll(actionDialog.user)} title="Grant All-Department Access?" description={actionDialog?.user?.fullName} confirmLabel="Grant Access" busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>This user will be able to operate across every department.</p>
      </ConfirmDialog>
    </section>
  )
}
