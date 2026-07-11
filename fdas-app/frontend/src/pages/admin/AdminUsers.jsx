import { useEffect, useState } from 'react'
import CSVExportButton from '../../components/CSVExportButton'
import { adminUsersApi } from '../../api/adminUsersApi'
import { departmentsApi } from '../../api/departmentsApi'
import { getApiError } from '../../api/client'

export default function AdminUsers() {
  const [users, setUsers] = useState([])
  const [departments, setDepartments] = useState([])
  const [modalUser, setModalUser] = useState(null)
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

  const saveAccess = async () => {
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
    }
  }

  const grantAll = async user => {
    setError('')
    try {
      await adminUsersApi.updateAccess(user.userId, { accessScope: 'AllDepartments', assignedDepartmentId: null })
      setMessage('All departments access granted.')
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to grant access.'))
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

      {message && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#d1fae5', borderColor: '#86efac', color: '#065f46' }}>{message}</div>}
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
                        <button onClick={() => grantAll(user)} className="px-3 py-2 rounded-lg text-xs font-bold text-white" style={{ backgroundColor: '#D4A017' }}>Grant All</button>
                        <button onClick={() => changeStatus(user)} className="px-3 py-2 rounded-lg text-xs font-bold border" style={{ borderColor: user.status === 'Disabled' ? '#065f46' : '#C4533A', color: user.status === 'Disabled' ? '#065f46' : '#C4533A' }}>
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

      {modalUser && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40">
          <div className="w-full max-w-md rounded-xl p-5 fdas-card">
            <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Change Access</h2>
            <p className="text-sm mt-1" style={{ color: '#55433b' }}>{modalUser.fullName}</p>
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
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setModalUser(null)} className="px-4 py-2 rounded-lg border font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Cancel</button>
              <button disabled={saving} onClick={saveAccess} className="px-4 py-2 rounded-lg font-bold text-white disabled:opacity-60" style={{ backgroundColor: '#C4533A' }}>{saving ? 'Saving...' : 'Save Access'}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
