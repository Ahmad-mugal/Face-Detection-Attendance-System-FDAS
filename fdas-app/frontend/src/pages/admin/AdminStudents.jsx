import { Link } from 'react-router-dom'
import { useCallback, useEffect, useMemo, useState } from 'react'
import CSVExportButton from '../../components/CSVExportButton'
import StatsCard from '../../components/StatsCard'
import StudentTable from '../../components/StudentTable'
import StudentStatusTabs from '../../components/StudentStatusTabs'
import StudentDetails from '../../components/StudentDetails'
import { studentsApi } from '../../api/studentsApi'
import { getApiError } from '../../api/client'
import Icon from '../../components/Icon'
import CameraEnrollment from '../../components/CameraEnrollment'
import DeepRecognitionDiagnosticCapture from '../../components/DeepRecognitionDiagnosticCapture'
import { ConfirmDialog, FormDialog, Modal } from '../../components/ui/Modal'
import Toast from '../../components/ui/Toast'
import PageHeader from '../../components/ui/PageHeader'
import { LoadingState } from '../../components/ui/AsyncState'

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

function matchesSearch(student, search) {
  const query = search.trim().toLowerCase()
  if (!query) return true
  return [student.fullName, student.rollNo, student.email, student.className, student.departmentName]
    .some(value => String(value || '').toLowerCase().includes(query))
}

export default function AdminStudents() {
  const [activeStudents, setActiveStudents] = useState([])
  const [inactiveStudents, setInactiveStudents] = useState([])
  const [activeView, setActiveView] = useState('active')
  const [searches, setSearches] = useState({ active: '', inactive: '' })
  const [modal, setModal] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadStudents = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [active, inactive] = await Promise.all([
        studentsApi.list({ status: 'active' }),
        studentsApi.list({ status: 'inactive' }),
      ])
      setActiveStudents(active)
      setInactiveStudents(inactive)
    } catch (err) {
      setError(getApiError(err, 'Unable to load students.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadStudents() }, [loadStudents])

  const currentStudents = activeView === 'active' ? activeStudents : inactiveStudents
  const visibleStudents = useMemo(
    () => currentStudents.filter(student => matchesSearch(student, searches[activeView])),
    [activeView, currentStudents, searches],
  )
  const mappedStudents = visibleStudents.map(mapStudent)
  const enrolled = [...activeStudents, ...inactiveStudents].filter(student => student.faceRegistered).length
  const selectedIsActive = modal?.student?.status === 'Active'

  const disableOrEnable = async student => {
    setError('')
    setSaving(true)
    try {
      if (student.status === 'Active') {
        await studentsApi.disable(student.studentId)
        setMessage('Student deactivated successfully.')
      } else {
        await studentsApi.enable(student.studentId)
        setMessage('Student reactivated successfully.')
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
      <PageHeader
        eyebrow="Student Management"
        title={activeView === 'active' ? 'Active Students' : 'Inactive Students'}
        description="Search, review, and manage enrolled student records while preserving attendance and face data."
        actions={<CSVExportButton data={visibleStudents} filename={`fdas_${activeView}_students.csv`} label={`Export ${activeView === 'active' ? 'Active' : 'Inactive'} CSV`} />}
      />

      {error && <div role="alert" className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Active Students" value={activeStudents.length} icon="groups" topBorder borderColor="#065f46" />
        <StatsCard title="Inactive Students" value={inactiveStudents.length} icon="person_off" iconColor="#934619" topBorder borderColor="#934619" />
        <StatsCard title="Face Enrolled" value={enrolled} icon="face" iconColor="#D4A017" topBorder borderColor="#D4A017" />
      </div>

      <StudentStatusTabs activeView={activeView} activeCount={activeStudents.length} inactiveCount={inactiveStudents.length} onChange={setActiveView} />

      <div className="fdas-card fdas-toolbar flex-col md:flex-row">
        <input
          value={searches[activeView]}
          onChange={event => setSearches(current => ({ ...current, [activeView]: event.target.value }))}
          placeholder={`Search ${activeView} students by name, email, class, or roll number`}
          className="fdas-input flex-1"
          aria-label={`Search ${activeView} students`}
        />
        {searches[activeView] && <button type="button" onClick={() => setSearches(current => ({ ...current, [activeView]: '' }))} className="fdas-button fdas-button-secondary">Clear</button>}
        <Link to="/admin/students/add" className="fdas-button fdas-button-primary"><Icon name="person_add" size={18} />Add Student</Link>
      </div>

      <div className="overflow-hidden fdas-card">
        {loading ? <LoadingState label="Loading students…" /> : <StudentTable students={mappedStudents} actionsEnabled onView={student => setModal({ type: 'view', student })} onDiagnose={student => setModal({ type: 'diagnostic', student })} onRecover={student => setModal({ type: 'recovery', student })} onEdit={student => setModal({ type: 'edit', student })} onDelete={student => setModal({ type: 'status', student })} />}
      </div>

      <Modal open={modal?.type === 'view'} onClose={() => setModal(null)} title="Student Details" description={modal?.student?.rollNumber} size="lg">
        <StudentDetails student={modal?.student} />
      </Modal>

      <Modal open={modal?.type === 'recovery'} onClose={() => setModal(null)} title="Deep Enrollment Recovery" description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} size="xl">
        {modal?.student && <CameraEnrollment recoveryMode studentId={modal.student.studentId} studentName={modal.student.name} onCompleted={result => { setMessage(`Deep recovery saved ${result.recoverySamples?.length || 0} samples. Deep readiness: ${result.deepCountAfter}/${result.requiredMinimum}.`); setModal(null); loadStudents() }} />}
      </Modal>

      <Modal open={modal?.type === 'diagnostic'} onClose={() => setModal(null)} title="Independent Deep Recognition Test" description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} size="wide">
        {modal?.student && <DeepRecognitionDiagnosticCapture student={modal.student} onCompleted={() => setMessage('Ten query-only deep diagnostic captures completed; no attendance or enrollment data was created.')} />}
      </Modal>

      <FormDialog open={modal?.type === 'edit'} onClose={() => setModal(null)} onSubmit={updateStudent} title="Edit Student" description={modal?.student?.rollNumber} submitLabel="Save Changes" busy={saving}>
        <label><span className="fdas-label">Full name</span><input autoFocus required value={modal?.student?.name || ''} onChange={event => setModal({ ...modal, student: { ...modal.student, name: event.target.value } })} className="fdas-input mt-1" /></label>
      </FormDialog>

      <ConfirmDialog open={modal?.type === 'status'} onClose={() => setModal(null)} onConfirm={() => disableOrEnable(modal.student)} title={selectedIsActive ? 'Deactivate Student?' : 'Reactivate Student?'} description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} confirmLabel={selectedIsActive ? 'Deactivate' : 'Reactivate Student'} destructive={selectedIsActive} busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>{selectedIsActive ? 'The student will no longer be eligible for attendance. Enrollment data and history will be preserved.' : 'This student will return to the Active Students view and become eligible for attendance again.'}</p>
      </ConfirmDialog>
    </section>
  )
}
