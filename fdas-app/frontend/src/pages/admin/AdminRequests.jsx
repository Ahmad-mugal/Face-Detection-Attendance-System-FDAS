import { useState } from 'react'
import StatsCard from '../../components/StatsCard'
import { DEPARTMENTS, PENDING_REQUESTS } from '../../data/dummyData'

export default function AdminRequests() {
  const [requests, setRequests] = useState(PENDING_REQUESTS)
  const [modal, setModal] = useState(null)

  const closeModal = () => setModal(null)
  const updateStatus = (id, status) => {
    setRequests(current => current.map(item => item.id === id ? { ...item, status } : item))
    closeModal()
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div>
        <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Access Control</p>
        <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Pending User Requests</h1>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Pending" value={requests.filter(item => item.status === 'pending').length} icon="pending_actions" />
        <StatsCard title="Approved Today" value={requests.filter(item => item.status === 'approved').length} icon="verified_user" iconColor="#D4A017" />
        <StatsCard title="Rejected" value={requests.filter(item => item.status === 'rejected').length} icon="block" iconColor="#C4533A" />
      </div>

      <div className="rounded-xl fdas-card overflow-hidden">
        <div className="fdas-table-wrap">
          <table className="fdas-table">
            <thead className="text-xs uppercase" style={{ color: '#C4533A', backgroundColor: '#fff1eb' }}>
              <tr>
                <th className="p-4">Name</th>
                <th className="p-4">Email</th>
                <th className="p-4">Requested Department</th>
                <th className="p-4">Requested Date</th>
                <th className="p-4">Status</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map(request => (
                <tr key={request.id} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                  <td className="p-4 font-bold" style={{ color: '#4A2B0F' }}>{request.fullName}</td>
                  <td className="p-4 text-sm" style={{ color: '#55433b' }}>{request.email}</td>
                  <td className="p-4">{request.requestedDepartment}</td>
                  <td className="p-4 text-sm">{new Date(request.requestedAt).toLocaleDateString()}</td>
                  <td className="p-4">
                    <span className="px-2.5 py-1 rounded-full text-xs font-bold capitalize" style={{ backgroundColor: request.status === 'pending' ? '#FFF0E6' : request.status === 'approved' ? '#d1fae5' : '#ffdad6', color: request.status === 'approved' ? '#065f46' : request.status === 'rejected' ? '#93000a' : '#934619' }}>
                      {request.status}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex justify-end gap-2">
                      <button onClick={() => setModal({ type: 'approve', request })} className="px-3 py-2 rounded-lg text-xs font-bold text-white" style={{ backgroundColor: '#D4A017' }}>Approve</button>
                      <button onClick={() => setModal({ type: 'reject', request })} className="px-3 py-2 rounded-lg text-xs font-bold border" style={{ borderColor: '#C4533A', color: '#C4533A' }}>Reject</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {modal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40">
          <div className="w-full max-w-md rounded-xl p-5 fdas-card">
            <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>{modal.type === 'approve' ? 'Approve User Request' : 'Reject User Request'}</h2>
            <p className="text-sm mt-1" style={{ color: '#55433b' }}>{modal.request.fullName} - {modal.request.email}</p>
            {modal.type === 'approve' ? (
              <div className="grid gap-4 mt-5">
                <label>
                  <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Department</span>
                  <select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.request.requestedDepartment}>
                    {DEPARTMENTS.map(item => <option key={item}>{item}</option>)}
                  </select>
                </label>
                <label>
                  <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Access Scope</span>
                  <select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }}>
                    <option>Department Only</option>
                    <option>All Departments</option>
                  </select>
                </label>
              </div>
            ) : (
              <p className="mt-5 rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>This will update only the dummy UI status for the viva demo.</p>
            )}
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={closeModal} className="px-4 py-2 rounded-lg border font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Cancel</button>
              <button onClick={() => updateStatus(modal.request.id, modal.type === 'approve' ? 'approved' : 'rejected')} className="px-4 py-2 rounded-lg font-bold text-white" style={{ backgroundColor: modal.type === 'approve' ? '#D4A017' : '#C4533A' }}>
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
