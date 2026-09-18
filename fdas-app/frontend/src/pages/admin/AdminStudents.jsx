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
import StudentImportDialog from '../../components/StudentImportDialog'

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
    hasEncodedFaceTemplates: student.hasEncodedFaceTemplates,
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
  const [faceFilter, setFaceFilter] = useState('all')
  const [modal, setModal] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [messageTone, setMessageTone] = useState('success')

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
    () => currentStudents.filter(student => {
      if (!matchesSearch(student, searches[activeView])) return false
      if (faceFilter === 'ready') return student.faceRegistered
      if (faceFilter === 'pending') return !student.faceRegistered && !student.hasEncodedFaceTemplates
      if (faceFilter === 'incomplete') return !student.faceRegistered && student.hasEncodedFaceTemplates
      return true
    }),
    [activeView, currentStudents, faceFilter, searches],
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
      setMessageTone('success')
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

  const deleteStudent = async student => {
    setSaving(true)
    setError('')
    try {
      const result = await studentsApi.delete(student.studentId)
      setMessage(result.message)
      setMessageTone('success')
      setModal(null)
      await loadStudents()
    } catch (err) {
      setMessage(getApiError(err, 'Unable to delete the student.'))
      setMessageTone('error')
      setModal(null)
    } finally {
      setSaving(false)
    }
  }

  const downloadTemplate = async () => {
    try {
      await studentsApi.downloadImportTemplate()
    } catch (err) {
      setError(getApiError(err, 'Unable to download the CSV template.'))
    }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <Toast message={message} tone={messageTone} onDismiss={() => setMessage('')} />
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
        <select value={faceFilter} onChange={event => setFaceFilter(event.target.value)} className="fdas-input md:max-w-[14rem]" aria-label="Face status filter">
          <option value="all">Face Status: All</option>
          <option value="ready">Face Ready</option>
          <option value="pending">Pending Face Registration</option>
          <option value="incomplete">Face Registration Incomplete</option>
        </select>
        {searches[activeView] && <button type="button" onClick={() => setSearches(current => ({ ...current, [activeView]: '' }))} className="fdas-button fdas-button-secondary">Clear</button>}
        <button type="button" onClick={downloadTemplate} className="fdas-button fdas-button-secondary"><Icon name="download" size={18} />CSV Template</button>
        <button type="button" onClick={() => setModal({ type: 'import' })} className="fdas-button fdas-button-outline"><Icon name="upload" size={18} />Import Students</button>
        <Link to="/admin/students/add" className="fdas-button fdas-button-primary"><Icon name="person_add" size={18} />Add Student</Link>
      </div>

      <div className="overflow-hidden fdas-card">
        {loading ? <LoadingState label="Loading students…" /> : <StudentTable students={mappedStudents} actionsEnabled onView={student => setModal({ type: 'view', student })} onDiagnose={student => setModal({ type: 'diagnostic', student })} onRecover={student => setModal({ type: 'recovery', student })} onRegisterFace={student => setModal({ type: 'enrollment', student })} onEdit={student => setModal({ type: 'edit', student })} onStatusChange={student => setModal({ type: 'status', student })} onPermanentDelete={student => setModal({ type: 'delete', student })} />}
      </div>

      <Modal open={modal?.type === 'view'} onClose={() => setModal(null)} title="Student Details" description={modal?.student?.rollNumber} size="lg">
        <StudentDetails student={modal?.student} />
      </Modal>

      <Modal open={modal?.type === 'recovery'} onClose={() => setModal(null)} title="Deep Enrollment Recovery" description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} size="xl">
        {modal?.student && <CameraEnrollment recoveryMode studentId={modal.student.studentId} studentName={modal.student.name} onCompleted={result => { setMessage(`Deep recovery saved ${result.recoverySamples?.length || 0} samples. Deep readiness: ${result.deepCountAfter}/${result.requiredMinimum}.`); setModal(null); loadStudents() }} />}
      </Modal>

      <Modal open={modal?.type === 'enrollment'} onClose={() => setModal(null)} title="Register Student Face" description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} size="xl">
        {modal?.student && <CameraEnrollment studentId={modal.student.studentId} studentName={modal.student.name} onCompleted={result => { setMessage(`Face enrollment completed. Saved samples: ${result.uploadedSamples?.length || 0}.`); setMessageTone('success'); setModal(null); loadStudents() }} />}
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

      <ConfirmDialog open={modal?.type === 'delete'} onClose={() => setModal(null)} onConfirm={() => deleteStudent(modal.student)} title="Delete Student?" description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} confirmLabel="Delete Student" destructive busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#ffdad6', color: '#93000a' }}>This permanently removes this student where permitted. Attendance history cannot be recovered. Students with protected history remain unchanged and should be deactivated instead.</p>
      </ConfirmDialog>

      <StudentImportDialog open={modal?.type === 'import'} onClose={() => setModal(null)} onImported={async result => { setMessage(`Student import completed: ${result.imported} imported.`); setMessageTone('success'); await loadStudents() }} />
    </section>
  )
}
