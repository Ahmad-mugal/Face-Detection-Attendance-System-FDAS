import { useCallback, useEffect, useMemo, useState } from 'react'
import { attendanceRecordsApi } from '../api/attendanceRecordsApi'
import { classesApi } from '../api/classesApi'
import { getApiError } from '../api/client'
import { departmentsApi } from '../api/departmentsApi'
import { useAuth } from '../context/useAuth'
import StatsCard from './StatsCard'
import Badge from './ui/Badge'
import PageHeader from './ui/PageHeader'
import { EmptyState, LoadingState } from './ui/AsyncState'

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function formatConfidence(value) {
  if (typeof value !== 'number') return '-'
  return value.toFixed(6)
}

function compactFilters(filters) {
  const studentSearch = filters.studentSearch.trim()
  return {
    departmentId: filters.departmentId || undefined,
    classId: filters.classId || undefined,
    studentId: /^\d+$/.test(studentSearch) ? Number(studentSearch) : undefined,
    dateFrom: filters.dateFrom || undefined,
    dateTo: filters.dateTo || undefined,
    status: filters.status || undefined,
  }
}

export default function AttendanceReportsPanel({ title = 'Attendance Reports', eyebrow = 'Reports', mode = 'admin' }) {
  const { assignedDepartmentId, assignedDepartmentName, hasAllDepartmentsAccess } = useAuth()
  const canChooseDepartment = mode === 'admin' || hasAllDepartmentsAccess()
  const departmentLabel = mode === 'user' && !canChooseDepartment ? 'Assigned Department' : 'Department'
  const [departments, setDepartments] = useState([])
  const [classes, setClasses] = useState([])
  const [records, setRecords] = useState([])
  const [summary, setSummary] = useState({
    totalRecords: 0,
    presentCount: 0,
    uniqueStudentsMarked: 0,
    averageRecognitionConfidence: null,
  })
  const [filters, setFilters] = useState({
    departmentId: canChooseDepartment ? '' : assignedDepartmentId || '',
    classId: '',
    studentSearch: '',
    dateFrom: '',
    dateTo: '',
    status: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [printGeneratedAt, setPrintGeneratedAt] = useState(() => new Date())

  useEffect(() => {
    departmentsApi.list()
      .then(items => {
        setDepartments(items)
        if (!canChooseDepartment && assignedDepartmentId) {
          setFilters(current => ({ ...current, departmentId: assignedDepartmentId }))
        }
      })
      .catch(err => setError(getApiError(err, 'Unable to load departments.')))
  }, [assignedDepartmentId, canChooseDepartment])

  useEffect(() => {
    const params = filters.departmentId ? { departmentId: filters.departmentId } : undefined
    classesApi.list(params)
      .then(items => setClasses(items.filter(item => item.status !== 'Archived')))
      .catch(err => setError(getApiError(err, 'Unable to load classes.')))
  }, [filters.departmentId])

  const loadReports = useCallback(async () => {
    setLoading(true)
    setError('')
    setMessage('')
    const apiFilters = compactFilters(filters)
    try {
      const [recordsData, summaryData] = await Promise.all([
        attendanceRecordsApi.list(apiFilters),
        attendanceRecordsApi.summary(apiFilters),
      ])
      setRecords(recordsData)
      setSummary(summaryData)
      if (recordsData.length === 0) setMessage('No attendance records found for the selected filters.')
    } catch (err) {
      setError(getApiError(err, 'Unable to load attendance records.'))
      setRecords([])
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    loadReports()
  }, [loadReports])

  const displayedRecords = useMemo(() => {
    const search = filters.studentSearch.trim().toLowerCase()
    if (!search || /^\d+$/.test(search)) return records
    return records.filter(record =>
      record.studentName?.toLowerCase().includes(search)
      || record.rollNo?.toLowerCase().includes(search)
    )
  }, [filters.studentSearch, records])

  const printSummary = useMemo(() => {
    const confidences = displayedRecords
      .map(record => record.recognitionConfidence)
      .filter(value => typeof value === 'number')
    return {
      totalRecords: displayedRecords.length,
      presentCount: displayedRecords.filter(record => record.status === 'Present').length,
      uniqueStudents: new Set(displayedRecords.map(record => record.studentId || record.rollNo)).size,
      averageConfidence: confidences.length
        ? confidences.reduce((total, value) => total + value, 0) / confidences.length
        : null,
    }
  }, [displayedRecords])

  const selectedDepartment = canChooseDepartment
    ? departments.find(department => String(department.departmentId) === String(filters.departmentId))?.departmentName || 'All Departments'
    : assignedDepartmentName || 'Assigned Department'
  const selectedClass = classes.find(item => String(item.classId) === String(filters.classId))?.className || 'All Classes'

  const updateFilter = (key, value) => {
    setFilters(current => ({
      ...current,
      [key]: value,
      ...(key === 'departmentId' ? { classId: '' } : {}),
    }))
  }

  const exportCsv = async () => {
    setError('')
    try {
      const blob = await attendanceRecordsApi.exportCsv(compactFilters(filters))
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'fdas_attendance_records.csv'
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(getApiError(err, 'Unable to export attendance records.'))
    }
  }

  const printReport = () => {
    setPrintGeneratedAt(new Date())
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => window.print()))
  }

  return (
    <section className="fdas-page fdas-print-report space-y-5 animate-fade-in-up">
      <div className="fdas-print-only fdas-print-report-header">
        <div className="fdas-print-brand">FDAS</div>
        <div className="fdas-print-report-title">Attendance Report</div>
        <p>Face Detection Attendance System</p>
      </div>

      <PageHeader className="fdas-no-print" eyebrow={eyebrow} title={title} description="Filter attendance activity, review recognition results, and export or print the current report view." actions={
        <>
          <button type="button" onClick={printReport} disabled={loading || displayedRecords.length === 0} className="fdas-button fdas-button-secondary">
            Print
          </button>
          <button type="button" onClick={exportCsv} disabled={records.length === 0} className="fdas-button fdas-button-warning">
            Export CSV
          </button>
        </>
      } />

      <div className="fdas-card fdas-card-section fdas-no-print">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-6 gap-3">
          <label>
            <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>{departmentLabel}</span>
            {canChooseDepartment ? (
              <select value={filters.departmentId} onChange={event => updateFilter('departmentId', event.target.value)} className="fdas-input mt-1">
                <option value="">All Departments</option>
                {departments.map(department => (
                  <option key={department.departmentId} value={department.departmentId}>{department.departmentName}</option>
                ))}
              </select>
            ) : (
              <div className="mt-1 rounded-lg border px-3 py-2.5 font-bold" style={{ borderColor: '#dbc1b7', color: '#4A2B0F', backgroundColor: '#fff' }}>
                {assignedDepartmentName || 'Assigned Department'}
              </div>
            )}
          </label>
          <label>
            <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Class</span>
            <select value={filters.classId} onChange={event => updateFilter('classId', event.target.value)} className="fdas-input mt-1">
              <option value="">All Classes</option>
              {classes.map(item => (
                <option key={item.classId} value={item.classId}>{item.className}</option>
              ))}
            </select>
          </label>
          <label>
            <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Date From</span>
            <input type="date" value={filters.dateFrom} onChange={event => updateFilter('dateFrom', event.target.value)} className="fdas-input mt-1" />
          </label>
          <label>
            <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Date To</span>
            <input type="date" value={filters.dateTo} onChange={event => updateFilter('dateTo', event.target.value)} className="fdas-input mt-1" />
          </label>
          <label>
            <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Student</span>
            <input value={filters.studentSearch} onChange={event => updateFilter('studentSearch', event.target.value)} className="fdas-input mt-1" placeholder="Name, roll no, or ID" />
          </label>
          <label>
            <span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Status</span>
            <select value={filters.status} onChange={event => updateFilter('status', event.target.value)} className="fdas-input mt-1">
              <option value="">All Status</option>
              <option value="Present">Present</option>
            </select>
          </label>
        </div>
      </div>

      <div className="rounded-xl p-3.5 text-xs border fdas-no-print" style={{ backgroundColor: '#fff1eb', borderColor: '#f0dfd8', color: '#55433b' }}>
        <p className="font-bold" style={{ color: '#4A2B0F' }}>Reports & Export Information:</p>
        <p className="mt-0.5" style={{ color: '#887369' }}>
          • <strong style={{ color: '#4A2B0F' }}>Liveness Status:</strong> Displayed directly from each stored attendance record (<code className="font-mono text-[11px]">Passed</code>, <code className="font-mono text-[11px]">Failed</code>, or <code className="font-mono text-[11px]">NotChecked</code>).
          <br />
          • <strong style={{ color: '#4A2B0F' }}>Export Availability:</strong> CSV export and browser printing are available for filtered records. The browser print dialog can also save as PDF where supported.
        </p>
      </div>

      {error && <div className="rounded-xl px-4 py-3 text-sm font-bold fdas-no-print" style={{ backgroundColor: '#ffdad6', color: '#93000a' }}>{error}</div>}
      {message && !error && <div className="rounded-xl px-4 py-3 text-sm font-bold fdas-no-print" style={{ backgroundColor: '#FFF0E6', color: '#795900' }}>{message}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 fdas-no-print">
        <StatsCard title="Total Records" value={summary.totalRecords} icon="fact_check" iconColor="#D4A017" />
        <StatsCard title="Present" value={summary.presentCount} icon="how_to_reg" iconColor="#065f46" />
        <StatsCard title="Unique Students" value={summary.uniqueStudentsMarked} icon="groups" iconColor="#E8924A" />
        <StatsCard title="Avg Confidence" value={summary.averageRecognitionConfidence === null ? '-' : summary.averageRecognitionConfidence.toFixed(3)} icon="verified" iconColor="#C4533A" />
      </div>

      <div className="fdas-print-only fdas-print-report-meta" data-print-report-meta>
        <dl>
          <div><dt>Department</dt><dd>{selectedDepartment}</dd></div>
          <div><dt>Class</dt><dd>{selectedClass}</dd></div>
          <div><dt>Date From</dt><dd>{filters.dateFrom || 'Any date'}</dd></div>
          <div><dt>Date To</dt><dd>{filters.dateTo || 'Any date'}</dd></div>
          <div><dt>Student / Filter</dt><dd>{filters.studentSearch.trim() || 'All Students'}</dd></div>
          <div><dt>Status</dt><dd>{filters.status || 'All Statuses'}</dd></div>
          <div><dt>Generated</dt><dd>{printGeneratedAt.toLocaleString()}</dd></div>
        </dl>
        <div className="fdas-print-summary">
          <div><span>Total Records</span><strong>{printSummary.totalRecords}</strong></div>
          <div><span>Present</span><strong>{printSummary.presentCount}</strong></div>
          <div><span>Unique Students</span><strong>{printSummary.uniqueStudents}</strong></div>
          <div><span>Average Confidence</span><strong>{printSummary.averageConfidence === null ? '-' : printSummary.averageConfidence.toFixed(3)}</strong></div>
        </div>
      </div>

      <div className="fdas-card overflow-hidden fdas-report-table-card">
        <div className="px-5 py-4 flex items-center justify-between border-b fdas-no-print" style={{ borderColor: '#f0dfd8' }}>
          <h2 className="fdas-section-title">Attendance Records</h2>
          <button onClick={loadReports} disabled={loading} className="fdas-button fdas-button-secondary fdas-button-sm">
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
        <div className="fdas-table-wrap">
          <table className="fdas-table" data-print-report-table>
            <thead>
              <tr>
                <th className="p-4">Student</th>
                <th className="p-4">Department</th>
                <th className="p-4">Class</th>
                <th className="p-4">Marked At</th>
                <th className="p-4">Status</th>
                <th className="p-4">Confidence</th>
                <th className="p-4">Liveness</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="7"><LoadingState label="Loading attendance records…" compact /></td></tr>
              ) : displayedRecords.length === 0 ? (
                <tr><td colSpan="7"><EmptyState title="No attendance records found" description="Adjust the filters and refresh the report." icon="fact_check" /></td></tr>
              ) : displayedRecords.map(record => (
                <tr key={record.attendanceRecordId} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                  <td className="p-4">
                    <div className="font-bold" style={{ color: '#4A2B0F' }}>{record.studentName}</div>
                    <div className="font-mono text-xs" style={{ color: '#887369' }}>{record.rollNo}</div>
                  </td>
                  <td className="p-4">{record.departmentName}</td>
                  <td className="p-4">{record.className}</td>
                  <td className="p-4">{formatDateTime(record.markedAt)}</td>
                  <td><Badge>{record.status}</Badge></td>
                  <td className="p-4 font-mono">{formatConfidence(record.recognitionConfidence)}</td>
                  <td><Badge tone={record.livenessStatus === 'Passed' ? 'success' : record.livenessStatus === 'Failed' ? 'danger' : 'neutral'}>{record.livenessStatus || 'NotChecked'}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
