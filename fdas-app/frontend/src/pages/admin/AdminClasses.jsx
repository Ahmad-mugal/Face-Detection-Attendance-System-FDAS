import { useCallback, useEffect, useState } from 'react'
import StatsCard from '../../components/StatsCard'
import { classesApi } from '../../api/classesApi'
import { departmentsApi } from '../../api/departmentsApi'
import { getApiError } from '../../api/client'
import Icon from '../../components/Icon'
import { ConfirmDialog, FormDialog } from '../../components/ui/Modal'
import Toast from '../../components/ui/Toast'

const emptyForm = { className: '', departmentId: '', yearSemester: '', section: 'A', status: 'Active' }

export default function AdminClasses() {
  const [classes, setClasses] = useState([])
  const [departments, setDepartments] = useState([])
  const [modal, setModal] = useState(null)
  const [statusDialog, setStatusDialog] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = {}
      if (search) params.search = search
      if (statusFilter) params.status = statusFilter
      const [classData, departmentData] = await Promise.all([
        classesApi.list(params),
        departmentsApi.list(),
      ])
      setClasses(classData)
      setDepartments(departmentData)
    } catch (err) {
      setError(getApiError(err, 'Unable to load classes.'))
    } finally {
      setLoading(false)
    }
  }, [search, statusFilter])

  useEffect(() => {
    loadData()
  }, [loadData])

  const openAdd = () => {
    setForm({ ...emptyForm, departmentId: String(departments[0]?.departmentId || '') })
    setModal({ mode: 'add' })
  }

  const openEdit = classItem => {
    setForm({
      className: classItem.className,
      departmentId: String(classItem.departmentId),
      yearSemester: classItem.yearSemester,
      section: classItem.section,
      status: classItem.status,
    })
    setModal({ mode: 'edit', classItem })
  }

  const submitClass = async event => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = { ...form, departmentId: Number(form.departmentId) }
      if (modal.mode === 'add') {
        await classesApi.create(payload)
        setMessage('Class created.')
      } else {
        await classesApi.update(modal.classItem.classId, payload)
        setMessage('Class updated.')
      }
      setModal(null)
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to save class.'))
    } finally {
      setSaving(false)
    }
  }

  const toggleArchive = async classItem => {
    setSaving(true)
    setError('')
    try {
      if (classItem.status === 'Archived') {
        await classesApi.activate(classItem.classId)
        setMessage('Class activated.')
      } else {
        await classesApi.archive(classItem.classId)
        setMessage('Class archived.')
      }
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to update class status.'))
    } finally {
      setSaving(false)
      setStatusDialog(null)
    }
  }

  const activeClasses = classes.filter(item => item.status === 'Active')
  const archivedClasses = classes.filter(item => item.status === 'Archived')

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Academic Setup</p>
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Manage Classes</h1>
        </div>
        <button onClick={openAdd} className="px-4 py-2.5 rounded-lg font-bold text-white flex items-center gap-2" style={{ backgroundColor: '#C4533A' }}>
          <Icon name="add" size={18} />
          Add New Class
        </button>
      </div>

      <Toast message={message} onDismiss={() => setMessage('')} />
      {error && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Active Classes" value={activeClasses.length} icon="school" />
        <StatsCard title="Archived" value={archivedClasses.length} icon="archive" iconColor="#E8924A" />
        <StatsCard title="Departments" value={departments.length} icon="domain" iconColor="#D4A017" />
      </div>

      <div className="fdas-card rounded-xl p-4 flex flex-col md:flex-row gap-3">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search classes" className="rounded-xl border px-4 py-3 flex-1" style={{ borderColor: '#dbc1b7' }} />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }}>
          <option value="">All statuses</option>
          <option value="Active">Active</option>
          <option value="Inactive">Inactive</option>
          <option value="Archived">Archived</option>
        </select>
        <button onClick={loadData} className="px-4 py-3 rounded-xl font-bold text-white" style={{ backgroundColor: '#934619' }}>Apply</button>
      </div>

      {loading ? (
        <div className="fdas-card rounded-xl p-8 text-center" style={{ color: '#887369' }}>Loading classes...</div>
      ) : classes.length === 0 ? (
        <div className="fdas-card rounded-xl p-8 text-center" style={{ color: '#887369' }}>No classes found.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {classes.map(item => (
            <article key={item.classId} className="rounded-xl p-5 border-t-[3px] fdas-card min-w-0" style={{ borderColor: item.status === 'Archived' ? '#887369' : '#D4A017' }}>
              <div className="flex justify-between gap-3">
                <h2 className="font-black text-lg truncate" style={{ color: '#4A2B0F' }}>{item.className}</h2>
                <span className="text-xs font-bold px-2 py-1 rounded-full whitespace-nowrap" style={{ backgroundColor: item.status === 'Archived' ? '#f0dfd8' : '#ffc641', color: '#715300' }}>{item.status}</span>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                <div><span style={{ color: '#887369' }}>Department</span><p className="font-bold" style={{ color: '#4A2B0F' }}>{item.departmentName}</p></div>
                <div><span style={{ color: '#887369' }}>Year/Semester</span><p className="font-bold" style={{ color: '#4A2B0F' }}>{item.yearSemester}</p></div>
                <div><span style={{ color: '#887369' }}>Section</span><p className="font-bold" style={{ color: '#4A2B0F' }}>{item.section}</p></div>
                <div><span style={{ color: '#887369' }}>Class ID</span><p className="font-bold" style={{ color: '#C4533A' }}>{item.classId}</p></div>
              </div>
              <div className="flex gap-2 mt-5">
                <button onClick={() => openEdit(item)} className="flex-1 px-3 py-2 rounded-lg text-sm font-bold border" style={{ borderColor: '#D4A017', color: '#715300' }}>Edit</button>
                <button onClick={() => setStatusDialog(item)} className="flex-1 px-3 py-2 rounded-lg text-sm font-bold border" style={{ borderColor: '#C4533A', color: '#C4533A' }}>{item.status === 'Archived' ? 'Activate' : 'Archive'}</button>
              </div>
            </article>
          ))}
        </div>
      )}

      <FormDialog open={Boolean(modal)} onClose={() => setModal(null)} onSubmit={submitClass} title={modal?.mode === 'add' ? 'Add New Class' : 'Edit Class'} submitLabel={modal?.mode === 'add' ? 'Create Class' : 'Save Changes'} busy={saving} size="lg">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-5">
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Class Name</span><input className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} value={form.className} onChange={e => setForm({ ...form, className: e.target.value })} /></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Department</span><select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} value={form.departmentId} onChange={e => setForm({ ...form, departmentId: e.target.value })}>{departments.map(item => <option key={item.departmentId} value={item.departmentId}>{item.departmentName}</option>)}</select></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Year/Semester</span><input className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} value={form.yearSemester} onChange={e => setForm({ ...form, yearSemester: e.target.value })} /></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Section</span><input className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} value={form.section} onChange={e => setForm({ ...form, section: e.target.value })} /></label>
              <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Status</span><select className="mt-1 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}><option>Active</option><option>Inactive</option><option>Archived</option></select></label>
            </div>
      </FormDialog>

      <ConfirmDialog open={Boolean(statusDialog)} onClose={() => setStatusDialog(null)} onConfirm={() => toggleArchive(statusDialog)} title={statusDialog?.status === 'Archived' ? 'Activate Class?' : 'Archive Class?'} description={statusDialog?.className} confirmLabel={statusDialog?.status === 'Archived' ? 'Activate' : 'Archive'} destructive={statusDialog?.status !== 'Archived'} busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>{statusDialog?.status === 'Archived' ? 'This class will become available for active academic workflows.' : 'The class will be removed from active selection while its historical data remains preserved.'}</p>
      </ConfirmDialog>
    </section>
  )
}
