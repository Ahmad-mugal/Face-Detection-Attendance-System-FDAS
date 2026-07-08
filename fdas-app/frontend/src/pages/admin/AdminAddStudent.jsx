import { useState } from 'react'
import CameraEnrollment from '../../components/CameraEnrollment'
import { CLASSES, DEPARTMENTS } from '../../data/dummyData'

const fieldClass = 'mt-1 w-full rounded-xl border px-4 py-3 outline-none text-sm'
const fieldStyle = { borderColor: '#dbc1b7', backgroundColor: '#ffffff', color: '#4A2B0F' }

export default function AdminAddStudent() {
  const [saved, setSaved] = useState(false)

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div>
        <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Enrollment</p>
        <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Add New Student</h1>
        <p className="text-sm mt-1" style={{ color: '#55433b' }}>Static form preview only. No student is saved in Phase 1.1.</p>
      </div>

      {saved && (
        <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#d1fae5', borderColor: '#86efac', color: '#065f46' }}>
          Dummy student profile is ready for demo. Backend save will be added in a later phase.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)] gap-5 min-w-0">
        <form className="rounded-xl p-5 sm:p-6 space-y-4 fdas-card min-w-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Full Name</span>
              <input className={fieldClass} style={fieldStyle} placeholder="Enter full name" />
            </label>
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Roll Number</span>
              <input className={fieldClass} style={fieldStyle} placeholder="CS-2026-001" />
            </label>
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Email optional</span>
              <input type="email" className={fieldClass} style={fieldStyle} placeholder="student@example.edu.pk" />
            </label>
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Phone optional</span>
              <input className={fieldClass} style={fieldStyle} placeholder="+92 300 0000000" />
            </label>
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Department</span>
              <select className={fieldClass} style={fieldStyle}>
                {DEPARTMENTS.map(department => <option key={department}>{department}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Class</span>
              <select className={fieldClass} style={fieldStyle}>
                {CLASSES.filter(item => !item.isArchived).map(item => <option key={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Semester/Year</span>
              <select className={fieldClass} style={fieldStyle}>
                {['1st Year', '2nd Year', '3rd Year', '4th Year', 'Semester 1', 'Semester 2', 'Semester 3', 'Semester 4'].map(item => <option key={item}>{item}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Section</span>
              <select className={fieldClass} style={fieldStyle}>
                {['A', 'B', 'C', 'Morning', 'Evening'].map(item => <option key={item}>{item}</option>)}
              </select>
            </label>
            <label className="block md:col-span-2">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Status</span>
              <select className={fieldClass} style={fieldStyle}>
                <option>Active</option>
                <option>Inactive</option>
                <option>Pending Face Enrollment</option>
              </select>
            </label>
          </div>

          <button type="button" onClick={() => setSaved(true)} className="w-full sm:w-auto px-5 py-3 rounded-xl font-bold text-white" style={{ backgroundColor: '#C4533A' }}>
            Save Student Profile
          </button>
        </form>
        <CameraEnrollment />
      </div>
    </section>
  )
}
