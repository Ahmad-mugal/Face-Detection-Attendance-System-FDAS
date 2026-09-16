import { Link } from 'react-router-dom'
import { useCallback, useEffect, useState } from 'react'
import CSVExportButton from '../../components/CSVExportButton'
import StatsCard from '../../components/StatsCard'
import StudentTable from '../../components/StudentTable'
import { studentsApi } from '../../api/studentsApi'
import { getApiError } from '../../api/client'
import Icon from '../../components/Icon'
import CameraEnrollment from '../../components/CameraEnrollment'
import DeepRecognitionDiagnosticCapture from '../../components/DeepRecognitionDiagnosticCapture'
import { ConfirmDialog, FormDialog, Modal } from '../../components/ui/Modal'
import Toast from '../../components/ui/Toast'

function mapStudent(student) {
  return {
    id: student.studentId,
    studentId: student.studentId,
    name: student.fullName,
    rollNumber: student.rollNo,
    className: student.className,
    department: student.departmentName,
    departmentId: student.departmentId,
    email: student.email || '',
    enrolled: student.faceRegistered,
    status: student.status,
  }
}

export default function AdminStudents() {
  const [students, setStudents] = useState([])
  const [modal, setModal] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadStudents = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setStudents(await studentsApi.list(search ? { search } : undefined))
    } catch (err) {
      setError(getApiError(err, 'Unable to load students.'))
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => { loadStudents() }, [loadStudents])

  const mappedStudents = students.map(mapStudent)
  const enrolled = students.filter(student => student.faceRegistered).length

  const disableOrEnable = async student => {
    setError('')
    setSaving(true)
    try {
      if (student.status === 'Disabled') {
        await studentsApi.enable(student.studentId)
        setMessage('Student activated successfully.')
      } else {
        await studentsApi.disable(student.studentId)
        setMessage('Student deactivated successfully.')
      }
      setModal(null)
      await loadStudents()
    } catch (err) {
      setError(getApiError(err, 'Unable to update student status.'))
    } finally {
      setSaving(false)
    }
  }

  const updateStudent = async event => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await studentsApi.update(modal.student.studentId, { fullName: modal.student.name })
      setMessage('Student updated successfully.')
      setModal(null)
      await loadStudents()
    } catch (err) {
      setError(getApiError(err, 'Unable to update student.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <Toast message={message} onDismiss={() => setMessage('')} />
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div><p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Student Management</p><h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>All Students</h1></div>
        <CSVExportButton data={students} filename="fdas_students.csv" />
      </div>

      {error && <div role="alert" className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Total Students" value={students.length} icon="groups" topBorder borderColor="#C4533A" />
        <StatsCard title="Face Enrolled" value={enrolled} icon="face" iconColor="#D4A017" topBorder borderColor="#D4A017" />
        <StatsCard title="Pending Enrollment" value={students.length - enrolled} icon="pending" iconColor="#E8924A" topBorder borderColor="#E8924A" />
      </div>

      <div className="fdas-card rounded-xl p-4 flex flex-col md:flex-row gap-3">
        <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search students by name or roll number" className="fdas-input flex-1" />
        <button onClick={loadStudents} className="fdas-button fdas-button-secondary">Search</button>
        <Link to="/admin/students/add" className="fdas-button fdas-button-primary"><Icon name="person_add" size={18} />Add Student</Link>
      </div>

      <div className="rounded-xl overflow-hidden fdas-card">
        {loading ? <div className="p-8 text-center" style={{ color: '#887369' }}>Loading students…</div> : <StudentTable students={mappedStudents} actionsEnabled onDiagnose={student => setModal({ type: 'diagnostic', student })} onRecover={student => setModal({ type: 'recovery', student })} onEdit={student => setModal({ type: 'edit', student })} onDelete={student => setModal({ type: 'status', student })} />}
      </div>

      <Modal open={modal?.type === 'recovery'} onClose={() => setModal(null)} title="Deep Enrollment Recovery" description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} size="xl">
        {modal?.student && <CameraEnrollment recoveryMode studentId={modal.student.studentId} studentName={modal.student.name} onCompleted={result => { setMessage(`Deep recovery saved ${result.recoverySamples?.length || 0} samples. Deep readiness: ${result.deepCountAfter}/${result.requiredMinimum}.`); setModal(null); loadStudents() }} />}
      </Modal>

      <Modal open={modal?.type === 'diagnostic'} onClose={() => setModal(null)} title="Independent Deep Recognition Test" description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} size="wide">
        {modal?.student && <DeepRecognitionDiagnosticCapture student={modal.student} onCompleted={() => setMessage('Ten query-only deep diagnostic captures completed; no attendance or enrollment data was created.')} />}
      </Modal>

      <FormDialog open={modal?.type === 'edit'} onClose={() => setModal(null)} onSubmit={updateStudent} title="Edit Student" description={modal?.student?.rollNumber} submitLabel="Save Changes" busy={saving}>
        <label><span className="fdas-label">Full name</span><input autoFocus required value={modal?.student?.name || ''} onChange={event => setModal({ ...modal, student: { ...modal.student, name: event.target.value } })} className="fdas-input mt-1" /></label>
      </FormDialog>

      <ConfirmDialog open={modal?.type === 'status'} onClose={() => setModal(null)} onConfirm={() => disableOrEnable(modal.student)} title={modal?.student?.status === 'Disabled' ? 'Activate Student?' : 'Deactivate Student?'} description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} confirmLabel={modal?.student?.status === 'Disabled' ? 'Activate' : 'Deactivate'} destructive={modal?.student?.status !== 'Disabled'} busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>{modal?.student?.status === 'Disabled' ? 'This student will become eligible for attendance again.' : 'The student will no longer be eligible for attendance. Enrollment data will be preserved.'}</p>
      </ConfirmDialog>
    </section>
  )
}
