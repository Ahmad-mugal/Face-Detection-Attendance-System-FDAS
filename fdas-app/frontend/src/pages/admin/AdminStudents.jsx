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
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadStudents = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = search ? { search } : undefined
      const data = await studentsApi.list(params)
      setStudents(data)
    } catch (err) {
      setError(getApiError(err, 'Unable to load students.'))
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => {
    loadStudents()
  }, [loadStudents])

  const mappedStudents = students.map(mapStudent)
  const enrolled = students.filter(student => student.faceRegistered).length

  const disableOrEnable = async student => {
    setError('')
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

  const updateStudent = async () => {
    try {
      await studentsApi.update(modal.student.studentId, { fullName: modal.student.name })
      setMessage('Student updated.')
      setModal(null)
      await loadStudents()
    } catch (err) {
      setError(getApiError(err, 'Unable to update student.'))
    }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Student Management</p>
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>All Students</h1>
        </div>
        <CSVExportButton data={students} filename="fdas_students.csv" />
      </div>

      {message && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#d1fae5', borderColor: '#86efac', color: '#065f46' }}>{message}</div>}
      {error && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Total Students" value={students.length} icon="groups" topBorder borderColor="#C4533A" />
        <StatsCard title="Face Enrolled" value={enrolled} icon="face" iconColor="#D4A017" topBorder borderColor="#D4A017" />
        <StatsCard title="Pending Enrollment" value={students.length - enrolled} icon="pending" iconColor="#E8924A" topBorder borderColor="#E8924A" />
      </div>

      <div className="fdas-card rounded-xl p-4 flex flex-col md:flex-row gap-3">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search students by name or roll number" className="rounded-xl border px-4 py-3 flex-1" style={{ borderColor: '#dbc1b7' }} />
        <button onClick={loadStudents} className="px-4 py-3 rounded-xl font-bold text-white" style={{ backgroundColor: '#934619' }}>Search</button>
        <Link to="/admin/students/add" className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-bold text-white" style={{ backgroundColor: '#C4533A' }}>
          <Icon name="person_add" size={18} />
          Add Student
        </Link>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ backgroundColor: '#fff8f6', boxShadow: '0 4px 20px rgba(232,146,74,0.12)' }}>
        {loading ? <div className="p-8 text-center" style={{ color: '#887369' }}>Loading students...</div> : <StudentTable students={mappedStudents} actionsEnabled onDiagnose={student => setModal({ type: 'diagnostic', student })} onRecover={student => setModal({ type: 'recovery', student })} onEdit={student => setModal({ type: 'edit', student })} onDelete={student => setModal({ type: 'status', student })} />}
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
            <h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>{modal.type === 'edit' ? 'Edit Student Name' : 'Change Student Status'}</h2>
            <p className="text-sm mt-1" style={{ color: '#55433b' }}>{modal.student.rollNumber}</p>
            {modal.type === 'edit' ? (
              <input value={modal.student.name} onChange={e => setModal({ ...modal, student: { ...modal.student, name: e.target.value } })} className="mt-5 w-full rounded-xl border px-4 py-3" style={{ borderColor: '#dbc1b7' }} />
            ) : (
              <p className="mt-5 rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>
                This will {modal.student.status === 'Disabled' ? 'enable' : 'disable'} the student record. No hard delete is performed.
              </p>
            )}
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setModal(null)} className="px-4 py-2 rounded-lg border font-bold" style={{ borderColor: '#dbc1b7', color: '#55433b' }}>Cancel</button>
              <button onClick={modal.type === 'edit' ? updateStudent : () => disableOrEnable(modal.student)} className="px-4 py-2 rounded-lg font-bold text-white" style={{ backgroundColor: '#C4533A' }}>Confirm</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
