import { useState } from 'react'
import CSVExportButton from '../../components/CSVExportButton'
import FilterBar from '../../components/FilterBar'
import { DEPARTMENTS, USERS } from '../../data/dummyData'

export default function AdminUsers() {
  const [users, setUsers] = useState(USERS)
  const [modalUser, setModalUser] = useState(null)

  const toggleStatus = user => {
    setUsers(current => current.map(item => item.id === user.id ? { ...item, status: item.status === 'active' ? 'disabled' : 'active' } : item))
  }

  const grantAll = user => {
    setUsers(current => current.map(item => item.id === user.id ? { ...item, department: null, accessScope: 'ALL_DEPARTMENTS' } : item))
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
      <FilterBar searchPlaceholder="Search users" showStatusFilter />
      <div className="rounded-xl fdas-card overflow-hidden">
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
                <tr key={user.id} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                  <td className="p-4 font-bold" style={{ color: '#4A2B0F' }}>{user.fullName}</td>
                  <td className="p-4 text-sm" style={{ color: '#55433b' }}>{user.email}</td>
                  <td className="p-4 capitalize">{user.role}</td>
                  <td className="p-4">{user.department || 'All Departments'}</td>
                  <td className="p-4">{user.accessScope === 'ALL_DEPARTMENTS' ? 'All Departments' : 'Department Only'}</td>
                  <td className="p-4">
                    <span className="px-2 py-1 rounded-full text-xs font-bold capitalize" style={{ backgroundColor: user.status === 'active' ? '#d1fae5' : '#ffdad6', color: user.status === 'active' ? '#065f46' : '#93000a' }}>{user.status}</span>
                  </td>
                  <td className="p-4">
                    <div className="flex justify-end gap-2 flex-wrap">
                      <button onClick={() => setModalUser(user)} className="px-3 py-2 rounded-lg text-xs font-bold border" style={{ borderColor: '#D4A017', color: '#715300' }}>Change Access</button>
                      <button onClick={() => grantAll(user)} className="px-3 py-2 rounded-lg text-xs font-bold text-white" style={{ backgroundColor: '#D4A017' }}>Grant All Departments</button>
                      <button onClick={() => toggleStatus(user)} className="px-3 py-2 rounded-lg text-xs font-bold border" style={{ borderColor: user.status === 'active' ? '#C4533A' : '#065f46', color: user.status === 'active' ? '#C4533A' : '#065f46' }}>
                        {user.status === 'active' ? 'Disable' : 'Enable'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {modalUser && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40">
          <div className="w-full max-w-md rounded-xl p-5 fdas-card">
            <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Change Access</h2>
            <p className="text-sm mt-1" style={{ color: '#55433b' }}>{modalUser.fullName}</p>
            <div className="grid gap-4 mt-5">
              <label>
                <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Assigned Department</span>
                <select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modalUser.department || DEPARTMENTS[0]}>
                  {DEPARTMENTS.map(item => <option key={item}>{item}</option>)}
                </select>
              </label>
              <label>
                <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Access Scope</span>
                <select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modalUser.accessScope === 'ALL_DEPARTMENTS' ? 'All Departments' : 'Department Only'}>
                  <option>Department Only</option>
                  <option>All Departments</option>
                </select>
              </label>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setModalUser(null)} className="px-4 py-2 rounded-lg border font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Cancel</button>
              <button onClick={() => setModalUser(null)} className="px-4 py-2 rounded-lg font-bold text-white" style={{ backgroundColor: '#C4533A' }}>Save Dummy Access</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
