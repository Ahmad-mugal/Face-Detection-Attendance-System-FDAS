import { useEffect, useState } from 'react'
import { studentsApi } from '../api/studentsApi'
import { getApiError } from '../api/client'
import Icon from './Icon'
import Badge from './ui/Badge'
import { Modal } from './ui/Modal'

function SummaryCard({ label, value, tone = 'neutral' }) {
  const colors = {
    success: ['#dcf7eb', '#08634d'],
    danger: ['#ffe3df', '#93000a'],
    warning: ['#fff4cc', '#715300'],
    neutral: ['#f3e8e3', '#55433b'],
  }
  const [backgroundColor, color] = colors[tone]
  return <div className="rounded-xl p-3 text-center" style={{ backgroundColor, color }}><strong className="block text-xl">{value}</strong><span className="text-xs font-bold">{label}</span></div>
}

function rowTone(status) {
  if (status === 'Ready') return 'success'
  if (status === 'Duplicate' || status === 'Existing') return 'warning'
  return 'danger'
}

export default function StudentImportDialog({ open, onClose, onImported }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) return
    setFile(null)
    setPreview(null)
    setResult(null)
    setError('')
  }, [open])

  const validate = async () => {
    if (!file) return
    setBusy(true)
    setError('')
    try {
      setPreview(await studentsApi.validateImport(file))
    } catch (err) {
      setError(getApiError(err, 'Unable to validate the CSV file.'))
    } finally {
      setBusy(false)
    }
  }

  const confirm = async () => {
    setBusy(true)
    setError('')
    try {
      const imported = await studentsApi.confirmImport(file)
      setResult(imported)
      await onImported?.(imported)
    } catch (err) {
      setError(getApiError(err, 'Unable to import students. No partial batch was retained.'))
    } finally {
      setBusy(false)
    }
  }

  const footer = result ? (
    <button type="button" onClick={onClose} className="fdas-button fdas-button-primary">Done</button>
  ) : preview ? (
    <>
      <button type="button" onClick={() => { setPreview(null); setError('') }} disabled={busy} className="fdas-button fdas-button-secondary">Back</button>
      <button type="button" onClick={confirm} disabled={busy || preview.validRows === 0} className="fdas-button fdas-button-primary">{busy ? 'Importing…' : `Import ${preview.validRows} Valid Student${preview.validRows === 1 ? '' : 's'}`}</button>
    </>
  ) : (
    <>
      <button type="button" onClick={onClose} disabled={busy} className="fdas-button fdas-button-secondary">Cancel</button>
      <button type="button" onClick={validate} disabled={busy || !file} className="fdas-button fdas-button-primary">{busy ? 'Validating…' : 'Validate CSV'}</button>
    </>
  )

  return (
    <Modal open={open} onClose={onClose} title="Import Students" description="Validate and preview a UTF-8 CSV before any student record is created." size="wide" busy={busy} footer={footer}>
      {error && <div role="alert" className="mb-4 rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      {result ? (
        <div className="space-y-5" data-import-step="complete">
          <div className="rounded-2xl border p-5 text-center" style={{ backgroundColor: '#dcf7eb', borderColor: '#a7e6cd', color: '#08634d' }}>
            <Icon name="check_circle" size={34} />
            <h3 className="mt-2 text-xl font-black">Students imported successfully.</h3>
            <p className="mt-1 text-sm">Imported: {result.imported} · Skipped invalid: {result.skippedInvalid} · Skipped duplicates/existing: {result.skippedDuplicates + result.skippedExisting}</p>
          </div>
          {result.students.length > 0 && <div className="fdas-table-wrap"><table className="fdas-table"><thead><tr><th>Name</th><th>Roll No.</th><th>Department</th><th>Face Status</th></tr></thead><tbody>{result.students.map(student => <tr key={student.studentId}><td>{student.fullName}</td><td>{student.rollNo}</td><td>{student.departmentName}</td><td><Badge tone="warning">Pending Face Registration</Badge></td></tr>)}</tbody></table></div>}
        </div>
      ) : preview ? (
        <div className="space-y-5" data-import-step="preview">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <SummaryCard label="Total Rows" value={preview.totalRows} />
            <SummaryCard label="Valid" value={preview.validRows} tone="success" />
            <SummaryCard label="Invalid" value={preview.invalidRows} tone="danger" />
            <SummaryCard label="Duplicate" value={preview.duplicateRows} tone="warning" />
            <SummaryCard label="Existing" value={preview.existingRows} tone="warning" />
          </div>
          {(preview.invalidRows + preview.duplicateRows + preview.existingRows) > 0 && <div className="flex justify-end"><button type="button" onClick={() => studentsApi.downloadImportErrors(file)} className="fdas-button fdas-button-outline fdas-button-sm"><Icon name="download" size={16} />Download Error Report</button></div>}
          <div className="fdas-table-wrap max-h-[22rem]"><table className="fdas-table min-w-[900px]"><thead><tr><th>Row</th><th>Name</th><th>Roll No.</th><th>Department</th><th>Class</th><th>Status</th><th>Issue</th></tr></thead><tbody>{preview.rows.map(row => <tr key={row.rowNumber}><td>{row.rowNumber}</td><td>{row.name || '—'}</td><td>{row.rollNo || '—'}</td><td>{row.department || '—'}</td><td>{row.className || '—'}</td><td><Badge tone={rowTone(row.status)}>{row.status}</Badge></td><td className="text-xs max-w-[18rem]">{row.issues.join('; ') || 'Ready to import'}</td></tr>)}</tbody></table></div>
        </div>
      ) : (
        <div className="space-y-5" data-import-step="upload">
          <ol className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-bold" style={{ color: '#6f5b52' }}><li className="rounded-lg bg-[#fff1eb] p-2">1. Select CSV</li><li className="rounded-lg bg-[#f3e8e3] p-2">2. Validate</li><li className="rounded-lg bg-[#f3e8e3] p-2">3. Preview</li><li className="rounded-lg bg-[#f3e8e3] p-2">4. Confirm</li></ol>
          <label className="block rounded-2xl border-2 border-dashed p-8 text-center cursor-pointer" style={{ borderColor: '#d4a017', backgroundColor: '#fff8f6' }}>
            <Icon name="upload" size={32} style={{ color: '#C4533A' }} />
            <span className="mt-3 block font-black" style={{ color: '#4A2B0F' }}>{file ? file.name : 'Choose Student CSV'}</span>
            <span className="mt-1 block text-xs" style={{ color: '#887369' }}>UTF-8 CSV · exact template headers · maximum 500 rows / 1 MB</span>
            <input data-modal-initial-focus type="file" accept=".csv,text/csv" className="sr-only" onChange={event => { setFile(event.target.files?.[0] || null); setPreview(null); setError('') }} />
          </label>
          <p className="text-sm leading-relaxed" style={{ color: '#6f5b52' }}>Selecting a file does not create records. FDAS validates every row on the server and writes only rows marked Ready after explicit confirmation.</p>
        </div>
      )}
    </Modal>
  )
}
