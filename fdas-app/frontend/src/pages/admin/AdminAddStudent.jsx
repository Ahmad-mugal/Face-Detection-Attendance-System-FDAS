import { useEffect, useMemo, useState } from 'react'
import CameraEnrollment from '../../components/CameraEnrollment'
import { classesApi } from '../../api/classesApi'
import { departmentsApi } from '../../api/departmentsApi'
import { studentsApi } from '../../api/studentsApi'
import { getApiError } from '../../api/client'

const fieldClass = 'mt-1 w-full rounded-xl border px-4 py-3 outline-none text-sm'
const fieldStyle = { borderColor: '#dbc1b7', backgroundColor: '#ffffff', color: '#4A2B0F' }
const emptyForm = { fullName: '', rollNo: '', email: '', phone: '', departmentId: '', classId: '', yearSemester: '', section: '', status: 'Active' }

export default function AdminAddStudent() {
  const [form, setForm] = useState(emptyForm)
  const [departments, setDepartments] = useState([])
  const [classes, setClasses] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadData() {
      setLoading(true)
      try {
        const [departmentData, classData] = await Promise.all([departmentsApi.list(), classesApi.list({ status: 'Active' })])
        setDepartments(departmentData)
        setClasses(classData)
        const firstDepartmentId = departmentData[0]?.departmentId || ''
        const firstClass = classData.find(item => item.departmentId === firstDepartmentId)
        setForm(current => ({
          ...current,
          departmentId: String(firstDepartmentId),
          classId: firstClass ? String(firstClass.classId) : '',
          yearSemester: firstClass?.yearSemester || '',
          section: firstClass?.section || '',
        }))
      } catch (err) {
        setError(getApiError(err, 'Unable to load form data.'))
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  const filteredClasses = useMemo(() => classes.filter(item => item.departmentId === Number(form.departmentId)), [classes, form.departmentId])

  const updateDepartment = departmentId => {
    const firstClass = classes.find(item => item.departmentId === Number(departmentId))
    setForm(current => ({
      ...current,
      departmentId,
      classId: firstClass ? String(firstClass.classId) : '',
      yearSemester: firstClass?.yearSemester || '',
      section: firstClass?.section || '',
    }))
  }

  const updateClass = classId => {
    const selectedClass = classes.find(item => item.classId === Number(classId))
    setForm(current => ({
      ...current,
      classId,
      yearSemester: selectedClass?.yearSemester || current.yearSemester,
      section: selectedClass?.section || current.section,
    }))
  }

  const submitStudent = async event => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')
    try {
      await studentsApi.create({
        fullName: form.fullName,
        rollNo: form.rollNo,
        email: form.email || null,
        phone: form.phone || null,
        departmentId: Number(form.departmentId),
        classId: Number(form.classId),
        yearSemester: form.yearSemester,
        section: form.section,
        status: form.status,
      })
      setMessage('Student profile saved. Face enrollment remains frontend-only in Phase 5.')
      setForm(current => ({ ...emptyForm, departmentId: current.departmentId, classId: current.classId, yearSemester: current.yearSemester, section: current.section, status: 'Active' }))
    } catch (err) {
      setError(getApiError(err, 'Unable to save student.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div>
        <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Enrollment</p>
        <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Add New Student</h1>
        <p className="text-sm mt-1" style={{ color: '#55433b' }}>Student profile saves to the backend. Face enrollment is still a Phase 5 dummy preview.</p>
      </div>

      {message && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#d1fae5', borderColor: '#86efac', color: '#065f46' }}>{message}</div>}
      {error && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      {loading ? (
        <div className="fdas-card rounded-xl p-8 text-center" style={{ color: '#887369' }}>Loading departments and classes...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)] gap-5 min-w-0">
          <form onSubmit={submitStudent} className="rounded-xl p-5 sm:p-6 space-y-4 fdas-card min-w-0">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="block"><span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Full Name</span><input required className={fieldClass} style={fieldStyle} value={form.fullName} onChange={e => setForm({ ...form, fullName: e.target.value })} /></label>
              <label className="block"><span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Roll Number</span><input required className={fieldClass} style={fieldStyle} value={form.rollNo} onChange={e => setForm({ ...form, rollNo: e.target.value })} placeholder="CS-2026-001" /></label>
              <label className="block"><span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Email optional</span><input type="email" className={fieldClass} style={fieldStyle} value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></label>
              <label className="block"><span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Phone optional</span><input className={fieldClass} style={fieldStyle} value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} /></label>
              <label className="block"><span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Department</span><select required className={fieldClass} style={fieldStyle} value={form.departmentId} onChange={e => updateDepartment(e.target.value)}>{departments.map(department => <option key={department.departmentId} value={department.departmentId}>{department.departmentName}</option>)}</select></label>
              <label className="block"><span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Class</span><select required className={fieldClass} style={fieldStyle} value={form.classId} onChange={e => updateClass(e.target.value)}>{filteredClasses.map(item => <option key={item.classId} value={item.classId}>{item.className}</option>)}</select></label>
              <label className="block"><span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Semester/Year</span><input className={fieldClass} style={fieldStyle} value={form.yearSemester} onChange={e => setForm({ ...form, yearSemester: e.target.value })} /></label>
              <label className="block"><span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Section</span><input className={fieldClass} style={fieldStyle} value={form.section} onChange={e => setForm({ ...form, section: e.target.value })} /></label>
              <label className="block md:col-span-2"><span className="text-xs font-bold uppercase tracking-wide" style={{ color: '#55433b' }}>Status</span><select className={fieldClass} style={fieldStyle} value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}><option>Active</option><option>Inactive</option><option>Disabled</option></select></label>
            </div>

            <button type="submit" disabled={saving || !form.classId} className="w-full sm:w-auto px-5 py-3 rounded-xl font-bold text-white disabled:opacity-60" style={{ backgroundColor: '#C4533A' }}>
              {saving ? 'Saving...' : 'Save Student Profile'}
            </button>
          </form>
          <CameraEnrollment />
        </div>
      )}
    </section>
  )
}
