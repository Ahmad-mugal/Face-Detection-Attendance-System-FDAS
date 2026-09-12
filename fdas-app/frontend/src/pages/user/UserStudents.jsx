import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import StudentTable from '../../components/StudentTable'
import { studentsApi } from '../../api/studentsApi'
import { getApiError } from '../../api/client'
import Icon from '../../components/Icon'
import CameraEnrollment from '../../components/CameraEnrollment'
import DeepRecognitionDiagnosticCapture from '../../components/DeepRecognitionDiagnosticCapture'

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

export default function UserStudents() {
  const [students, setStudents] = useState([])
  const [modal, setModal] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadStudents = async () => {
    setLoading(true)
    setError('')
    try {
      setStudents(await studentsApi.list())
    } catch (err) {
      setError(getApiError(err, 'Unable to load department students.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStudents()
  }, [])

  const disableOrEnable = async student => {
    try {
      if (student.status === 'Disabled') {
        await studentsApi.enable(student.studentId)
        setMessage('Student enabled.')
      } else {
        await studentsApi.disable(student.studentId)
        setMessage('Student disabled.')
      }
      setModal(null)
      await loadStudents()
    } catch (err) {
      setError(getApiError(err, 'Unable to update student.'))
    }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div>
        <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Department Students</p>
        <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Students</h1>
      </div>
      {message && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#d1fae5', borderColor: '#86efac', color: '#065f46' }}>{message}</div>}
      {error && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="fdas-card rounded-xl p-4 flex justify-end">
        <Link to="/user/students/add" className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-bold text-sm text-white" style={{ backgroundColor: '#C4533A' }}>
          <Icon name="person_add" size={18} />
          Add Student
        </Link>
      </div>
      <div className="rounded-xl overflow-hidden" style={{ backgroundColor: '#fff8f6', boxShadow: '0 4px 20px rgba(232,146,74,0.12)' }}>
        {loading ? <div className="p-8 text-center" style={{ color: '#887369' }}>Loading students...</div> : <StudentTable students={students.map(mapStudent)} actionsEnabled onDiagnose={student => setModal({ type: 'diagnostic', student })} onRecover={student => setModal({ type: 'recovery', student })} onDelete={student => setModal({ type: 'status', student })} />}
      </div>
      {modal?.type === 'recovery' && (
        <div className="fixed inset-0 z-[80] overflow-y-auto bg-black/40 p-4">
          <div className="mx-auto my-6 w-full max-w-3xl rounded-xl p-5 fdas-card">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Deep Enrollment Recovery</h2>
                <p className="text-sm mt-1" style={{ color: '#55433b' }}>{modal.student.name} — {modal.student.rollNumber}</p>
              </div>
              <button onClick={() => setModal(null)} className="rounded-lg border px-3 py-2 font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Close</button>
            </div>
            <CameraEnrollment
              recoveryMode
              studentId={modal.student.studentId}
              studentName={modal.student.name}
              onCompleted={result => {
                setMessage(`Deep recovery saved ${result.recoverySamples?.length || 0} samples. Deep readiness: ${result.deepCountAfter}/${result.requiredMinimum}.`)
                setModal(null)
                loadStudents()
              }}
            />
          </div>
        </div>
      )}
      {modal?.type === 'diagnostic' && (
        <div className="fixed inset-0 z-[80] overflow-y-auto bg-black/40 p-4">
          <div className="mx-auto my-6 w-full max-w-5xl rounded-xl p-5 fdas-card">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Independent Deep Recognition Test</h2>
                <p className="text-sm mt-1" style={{ color: '#55433b' }}>{modal.student.name} — {modal.student.rollNumber}</p>
              </div>
              <button onClick={() => setModal(null)} className="rounded-lg border px-3 py-2 font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Close</button>
            </div>
            <DeepRecognitionDiagnosticCapture student={modal.student} onCompleted={() => setMessage('Ten query-only deep diagnostic captures completed; no attendance or enrollment data was created.')} />
          </div>
        </div>
      )}
      {modal && !['recovery', 'diagnostic'].includes(modal.type) && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40">
          <div className="w-full max-w-md rounded-xl p-5 fdas-card">
            <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Change Student Status</h2>
            <p className="text-sm mt-1" style={{ color: '#55433b' }}>{modal.student.name} - {modal.student.rollNumber}</p>
            <p className="mt-5 rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>This uses the backend enable/disable endpoint. Face enrollment remains dummy.</p>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg border font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Cancel</button>
              <button onClick={() => disableOrEnable(modal.student)} className="px-4 py-2 rounded-lg font-bold text-white" style={{ backgroundColor: '#C4533A' }}>Confirm</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
