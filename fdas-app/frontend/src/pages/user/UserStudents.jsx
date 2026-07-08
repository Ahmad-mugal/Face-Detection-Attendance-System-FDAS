import { Link } from 'react-router-dom'
import { useState } from 'react'
import FilterBar from '../../components/FilterBar'
import StudentTable from '../../components/StudentTable'
import { STUDENTS } from '../../data/dummyData'

export default function UserStudents() {
  const [modal, setModal] = useState(null)
  const departmentStudents = STUDENTS.filter(student => student.department === 'Computer Science')

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div>
        <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Department Students</p>
        <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Students</h1>
      </div>
      <FilterBar
        searchPlaceholder="Search department students"
        showDeptFilter={false}
        showStatusFilter
        actionButton={(
          <Link to="/user/students/add" className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-bold text-sm text-white" style={{ backgroundColor: '#C4533A' }}>
            <span className="material-symbols-outlined text-[18px]">person_add</span>
            Add Student
          </Link>
        )}
      />
      <div className="rounded-xl overflow-hidden" style={{ backgroundColor: '#fff8f6', boxShadow: '0 4px 20px rgba(232,146,74,0.12)' }}>
        <StudentTable students={departmentStudents} actionsEnabled onEdit={student => setModal({ type: 'edit', student })} onDelete={student => setModal({ type: 'archive', student })} />
      </div>
      {modal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40">
          <div className="w-full max-w-md rounded-xl p-5 fdas-card">
            <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>{modal.type === 'edit' ? 'Edit Student' : 'Archive Student'}</h2>
            <p className="text-sm mt-1" style={{ color: '#55433b' }}>{modal.student.name} - {modal.student.rollNumber}</p>
            <p className="mt-5 rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>
              Placeholder modal only. Operator changes remain static in Phase 1.1.
            </p>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg border font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Cancel</button>
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg font-bold text-white" style={{ backgroundColor: '#C4533A' }}>Confirm</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
