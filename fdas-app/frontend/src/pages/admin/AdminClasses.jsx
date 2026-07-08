import { useState } from 'react'
import FilterBar from '../../components/FilterBar'
import StatsCard from '../../components/StatsCard'
import { CLASSES, DEPARTMENTS } from '../../data/dummyData'

export default function AdminClasses() {
  const [classes, setClasses] = useState(CLASSES.map((item, index) => ({
    ...item,
    year: item.name.match(/\d{4}/)?.[0] || '2026',
    section: index % 2 === 0 ? 'A' : 'B',
  })))
  const [modal, setModal] = useState(null)
  const activeClasses = classes.filter(item => !item.isArchived)

  const archiveClass = classItem => {
    setClasses(current => current.map(item => item.id === classItem.id ? { ...item, isArchived: !item.isArchived } : item))
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Academic Setup</p>
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Manage Classes</h1>
        </div>
        <button onClick={() => setModal({ mode: 'add' })} className="px-4 py-2.5 rounded-lg font-bold text-white flex items-center gap-2" style={{ backgroundColor: '#C4533A' }}>
          <span className="material-symbols-outlined text-[18px]">add</span>
          Add New Class
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Active Classes" value={activeClasses.length} icon="school" />
        <StatsCard title="Archived" value={classes.length - activeClasses.length} icon="archive" iconColor="#E8924A" />
        <StatsCard title="Students" value={classes.reduce((sum, item) => sum + item.students, 0)} icon="groups" iconColor="#D4A017" />
      </div>

      <FilterBar searchPlaceholder="Search classes" showStatusFilter />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {classes.map(item => (
          <article key={item.id} className="rounded-xl p-5 border-t-[3px] fdas-card min-w-0" style={{ borderColor: item.isArchived ? '#887369' : '#D4A017' }}>
            <div className="flex justify-between gap-3">
              <h2 className="font-black text-lg truncate" style={{ color: '#4A2B0F' }}>{item.name}</h2>
              <span className="text-xs font-bold px-2 py-1 rounded-full whitespace-nowrap" style={{ backgroundColor: item.isArchived ? '#f0dfd8' : '#ffc641', color: '#715300' }}>{item.isArchived ? 'Archived' : 'Active'}</span>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
              <div><span style={{ color: '#887369' }}>Department</span><p className="font-bold" style={{ color: '#4A2B0F' }}>{item.department}</p></div>
              <div><span style={{ color: '#887369' }}>Year/Semester</span><p className="font-bold" style={{ color: '#4A2B0F' }}>{item.year}</p></div>
              <div><span style={{ color: '#887369' }}>Section</span><p className="font-bold" style={{ color: '#4A2B0F' }}>{item.section}</p></div>
              <div><span style={{ color: '#887369' }}>Students</span><p className="font-bold" style={{ color: '#C4533A' }}>{item.students}</p></div>
            </div>
            <div className="flex gap-2 mt-5">
              <button onClick={() => setModal({ mode: 'edit', classItem: item })} className="flex-1 px-3 py-2 rounded-lg text-sm font-bold border" style={{ borderColor: '#D4A017', color: '#715300' }}>Edit</button>
              <button onClick={() => archiveClass(item)} className="flex-1 px-3 py-2 rounded-lg text-sm font-bold border" style={{ borderColor: '#C4533A', color: '#C4533A' }}>{item.isArchived ? 'Restore' : 'Archive'}</button>
            </div>
          </article>
        ))}
      </div>

      {modal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40">
          <div className="w-full max-w-lg rounded-xl p-5 fdas-card">
            <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>{modal.mode === 'add' ? 'Add New Class' : 'Edit Class'}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-5">
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Class Name</span><input className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.classItem?.name || ''} placeholder="BSCS-2026" /></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Department</span><select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.classItem?.department || DEPARTMENTS[0]}>{DEPARTMENTS.map(item => <option key={item}>{item}</option>)}</select></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Year/Semester</span><input className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.classItem?.year || ''} placeholder="2026" /></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Section</span><select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} defaultValue={modal.classItem?.section || 'A'}><option>A</option><option>B</option><option>C</option><option>Morning</option><option>Evening</option></select></label>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg border font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Cancel</button>
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg font-bold text-white" style={{ backgroundColor: '#C4533A' }}>Save Dummy Class</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
