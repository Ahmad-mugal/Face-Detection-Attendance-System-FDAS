import { useState } from 'react'
import { DEPARTMENTS, TIMINGS } from '../../data/dummyData'

export default function AdminTiming() {
  const [timings, setTimings] = useState(TIMINGS.map((item, index) => ({
    ...item,
    gracePeriod: index % 2 === 0 ? '10 min' : '5 min',
    status: index === 1 ? 'inactive' : 'active',
    autoStop: index % 3 !== 0,
  })))
  const [modal, setModal] = useState(null)

  const toggleTiming = timing => {
    setTimings(current => current.map(item => item.id === timing.id ? { ...item, status: item.status === 'active' ? 'inactive' : 'active' } : item))
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Scheduling</p>
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Attendance Timing</h1>
        </div>
        <button onClick={() => setModal({ mode: 'add' })} className="px-4 py-2.5 rounded-lg font-bold text-white flex items-center gap-2" style={{ backgroundColor: '#C4533A' }}>
          <span className="material-symbols-outlined text-[18px]">add</span>
          Add Time Window
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {timings.map(timing => (
          <article key={timing.id} className="rounded-xl p-5 fdas-card min-w-0">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="font-black" style={{ color: '#4A2B0F' }}>{timing.name}</h2>
                <p className="text-sm" style={{ color: '#55433b' }}>{timing.department}</p>
              </div>
              <span className="px-2.5 py-1 rounded-full text-xs font-bold capitalize" style={{ backgroundColor: timing.status === 'active' ? '#d1fae5' : '#ffdad6', color: timing.status === 'active' ? '#065f46' : '#93000a' }}>{timing.status}</span>
            </div>
            <div className="mt-5 rounded-xl p-4 text-center" style={{ backgroundColor: '#FFF0E6' }}>
              <span className="text-2xl font-black" style={{ color: '#C4533A' }}>{timing.startTime}</span>
              <span className="mx-3" style={{ color: '#887369' }}>to</span>
              <span className="text-2xl font-black" style={{ color: '#934619' }}>{timing.endTime}</span>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
              <div><span style={{ color: '#887369' }}>Grace Period</span><p className="font-bold" style={{ color: '#4A2B0F' }}>{timing.gracePeriod}</p></div>
              <div><span style={{ color: '#887369' }}>Auto-stop</span><p className="font-bold" style={{ color: '#4A2B0F' }}>{timing.autoStop ? 'Enabled' : 'Disabled'}</p></div>
            </div>
            <div className="flex gap-2 mt-5">
              <button onClick={() => setModal({ mode: 'edit', timing })} className="flex-1 px-3 py-2 rounded-lg text-sm font-bold border" style={{ borderColor: '#D4A017', color: '#715300' }}>Edit</button>
              <button onClick={() => toggleTiming(timing)} className="flex-1 px-3 py-2 rounded-lg text-sm font-bold border" style={{ borderColor: '#C4533A', color: '#C4533A' }}>{timing.status === 'active' ? 'Deactivate' : 'Activate'}</button>
            </div>
          </article>
        ))}
      </div>

      {modal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40">
          <div className="w-full max-w-lg rounded-xl p-5 fdas-card">
            <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>{modal.mode === 'add' ? 'Add Time Window' : 'Edit Time Window'}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-5">
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Department</span><select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.timing?.department || DEPARTMENTS[0]}>{DEPARTMENTS.map(item => <option key={item}>{item}</option>)}</select></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Grace Period</span><input className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.timing?.gracePeriod || '10 min'} /></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Start Time</span><input type="time" className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.timing?.startTime || '08:00'} /></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>End Time</span><input type="time" className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.timing?.endTime || '09:30'} /></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Status</span><select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.timing?.status || 'active'}><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Auto-stop</span><select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.timing?.autoStop ? 'Enabled' : 'Disabled'}><option>Enabled</option><option>Disabled</option></select></label>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg border font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Cancel</button>
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg font-bold text-white" style={{ backgroundColor: '#C4533A' }}>Save Dummy Window</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
