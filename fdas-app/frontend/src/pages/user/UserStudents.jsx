import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import StudentTable from '../../components/StudentTable'
import { studentsApi } from '../../api/studentsApi'
import { getApiError } from '../../api/client'
import Icon from '../../components/Icon'
import CameraEnrollment from '../../components/CameraEnrollment'
import { ConfirmDialog, Modal } from '../../components/ui/Modal'
import Toast from '../../components/ui/Toast'

function mapStudent(student) {
  return { id: student.studentId, studentId: student.studentId, name: student.fullName, rollNumber: student.rollNo, className: student.className, department: student.departmentName, departmentId: student.departmentId, email: student.email || '', enrolled: student.faceRegistered, status: student.status }
}

export default function UserStudents() {
  const [students, setStudents] = useState([])
  const [modal, setModal] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadStudents = async () => {
    setLoading(true)
    setError('')
    try { setStudents(await studentsApi.list()) } catch (err) { setError(getApiError(err, 'Unable to load department students.')) } finally { setLoading(false) }
  }

  useEffect(() => { loadStudents() }, [])

  const disableOrEnable = async student => {
    setSaving(true)
    setError('')
    try {
      if (student.status === 'Disabled') { await studentsApi.enable(student.studentId); setMessage('Student activated successfully.') }
      else { await studentsApi.disable(student.studentId); setMessage('Student deactivated successfully.') }
      setModal(null)
      await loadStudents()
    } catch (err) { setError(getApiError(err, 'Unable to update student status.')) } finally { setSaving(false) }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <Toast message={message} onDismiss={() => setMessage('')} />
      <div><p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Department Students</p><h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Students</h1></div>
      {error && <div role="alert" className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}
      <div className="fdas-card rounded-xl p-4 flex justify-end"><Link to="/user/students/add" className="fdas-button fdas-button-primary"><Icon name="person_add" size={18} />Add Student</Link></div>
      <div className="rounded-xl overflow-hidden fdas-card">{loading ? <div className="p-8 text-center" style={{ color: '#887369' }}>Loading students…</div> : <StudentTable students={students.map(mapStudent)} actionsEnabled onRecover={student => setModal({ type: 'recovery', student })} onDelete={student => setModal({ type: 'status', student })} />}</div>

      <Modal open={modal?.type === 'recovery'} onClose={() => setModal(null)} title="Deep Enrollment Recovery" description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} size="xl">
        {modal?.student && <CameraEnrollment recoveryMode studentId={modal.student.studentId} studentName={modal.student.name} onCompleted={result => { setMessage(`Deep recovery saved ${result.recoverySamples?.length || 0} samples. Deep readiness: ${result.deepCountAfter}/${result.requiredMinimum}.`); setModal(null); loadStudents() }} />}
      </Modal>
      <ConfirmDialog open={modal?.type === 'status'} onClose={() => setModal(null)} onConfirm={() => disableOrEnable(modal.student)} title={modal?.student?.status === 'Disabled' ? 'Activate Student?' : 'Deactivate Student?'} description={modal?.student ? `${modal.student.name} — ${modal.student.rollNumber}` : ''} confirmLabel={modal?.student?.status === 'Disabled' ? 'Activate' : 'Deactivate'} destructive={modal?.student?.status !== 'Disabled'} busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>{modal?.student?.status === 'Disabled' ? 'This student will become eligible for attendance again.' : 'The student will no longer be eligible for attendance. Enrollment data will be preserved.'}</p>
      </ConfirmDialog>
    </section>
  )
}
