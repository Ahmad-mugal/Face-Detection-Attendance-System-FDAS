import { useEffect, useState } from 'react'
import { attendanceTimeWindowsApi } from '../../api/attendanceTimeWindowsApi'
import { departmentsApi } from '../../api/departmentsApi'
import { getApiError } from '../../api/client'
import Icon from '../../components/Icon'
import { ConfirmDialog, FormDialog } from '../../components/ui/Modal'
import Toast from '../../components/ui/Toast'
import Badge from '../../components/ui/Badge'
import PageHeader from '../../components/ui/PageHeader'
import { EmptyState, LoadingState } from '../../components/ui/AsyncState'

const emptyForm = { departmentId: '', startTime: '08:00', endTime: '09:00', graceMinutes: 10, status: 'Active' }

export default function AdminTiming() {
  const [timings, setTimings] = useState([])
  const [departments, setDepartments] = useState([])
  const [modal, setModal] = useState(null)
  const [statusDialog, setStatusDialog] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [windowData, departmentData] = await Promise.all([
        attendanceTimeWindowsApi.list(),
        departmentsApi.list(),
      ])
      setTimings(windowData)
      setDepartments(departmentData)
    } catch (err) {
      setError(getApiError(err, 'Unable to load attendance time windows.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const openAdd = () => {
    setForm({ ...emptyForm, departmentId: String(departments[0]?.departmentId || '') })
    setModal({ mode: 'add' })
  }

  const openEdit = timing => {
    setForm({
      departmentId: String(timing.departmentId),
      startTime: timing.startTime.slice(0, 5),
      endTime: timing.endTime.slice(0, 5),
      graceMinutes: timing.graceMinutes,
      status: timing.status,
    })
    setModal({ mode: 'edit', timing })
  }

  const submitTiming = async event => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = {
        departmentId: Number(form.departmentId),
        startTime: `${form.startTime}:00`,
        endTime: `${form.endTime}:00`,
        graceMinutes: Number(form.graceMinutes),
        status: form.status,
      }
      if (modal.mode === 'add') {
        await attendanceTimeWindowsApi.create(payload)
        setMessage('Attendance time window created.')
      } else {
        await attendanceTimeWindowsApi.update(modal.timing.windowId, payload)
        setMessage('Attendance time window updated.')
      }
      setModal(null)
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to save attendance time window.'))
    } finally {
      setSaving(false)
    }
  }

  const toggleTiming = async timing => {
    setSaving(true)
    setError('')
    try {
      if (timing.status === 'Active') {
        await attendanceTimeWindowsApi.deactivate(timing.windowId)
        setMessage('Time window deactivated.')
      } else {
        await attendanceTimeWindowsApi.activate(timing.windowId)
        setMessage('Time window activated.')
      }
      await loadData()
    } catch (err) {
      setError(getApiError(err, 'Unable to update time window.'))
    } finally {
      setSaving(false)
      setStatusDialog(null)
    }
  }

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <PageHeader eyebrow="Scheduling" title="Attendance Timing" description="Configure department attendance windows and grace periods." actions={
        <button onClick={openAdd} className="fdas-button fdas-button-primary">
          <Icon name="add" size={18} />
          Add Time Window
        </button>
      } />

      <Toast message={message} onDismiss={() => setMessage('')} />
      {error && <div className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}

      {loading ? (
        <div className="fdas-card"><LoadingState label="Loading attendance time windows…" /></div>
      ) : timings.length === 0 ? (
        <div className="fdas-card"><EmptyState title="No time windows found" description="Add a time window to make attendance available for a department." icon="schedule" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {timings.map(timing => (
            <article key={timing.windowId} className="p-4 fdas-card min-w-0">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-black" style={{ color: '#4A2B0F' }}>Window #{timing.windowId}</h2>
                  <p className="text-sm" style={{ color: '#55433b' }}>{timing.departmentName}</p>
                </div>
                <Badge>{timing.status}</Badge>
              </div>
              <div className="mt-5 rounded-xl p-4 text-center" style={{ backgroundColor: '#FFF0E6' }}>
                <span className="text-2xl font-black" style={{ color: '#C4533A' }}>{timing.startTime.slice(0, 5)}</span>
                <span className="mx-3" style={{ color: '#887369' }}>to</span>
                <span className="text-2xl font-black" style={{ color: '#934619' }}>{timing.endTime.slice(0, 5)}</span>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                <div><span style={{ color: '#887369' }}>Grace Period</span><p className="font-bold" style={{ color: '#4A2B0F' }}>{timing.graceMinutes} min</p></div>
                <div><span style={{ color: '#887369' }}>Scope</span><p className="font-bold" style={{ color: '#4A2B0F' }}>Department</p></div>
              </div>
              <div className="flex gap-2 mt-5">
                <button onClick={() => openEdit(timing)} className="fdas-button fdas-button-secondary fdas-button-sm flex-1">Edit</button>
                <button onClick={() => setStatusDialog(timing)} className="fdas-button fdas-button-outline fdas-button-sm flex-1">{timing.status === 'Active' ? 'Deactivate' : 'Activate'}</button>
              </div>
            </article>
          ))}
        </div>
      )}

      <FormDialog open={Boolean(modal)} onClose={() => setModal(null)} onSubmit={submitTiming} title={modal?.mode === 'add' ? 'Add Time Window' : 'Edit Time Window'} submitLabel={modal?.mode === 'add' ? 'Create Window' : 'Save Changes'} busy={saving} size="lg">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label><span className="fdas-label">Department</span><select className="fdas-input mt-1" value={form.departmentId} onChange={e => setForm({ ...form, departmentId: e.target.value })}>{departments.map(item => <option key={item.departmentId} value={item.departmentId}>{item.departmentName}</option>)}</select></label>
              <label><span className="fdas-label">Grace Minutes</span><input type="number" min="0" className="fdas-input mt-1" value={form.graceMinutes} onChange={e => setForm({ ...form, graceMinutes: e.target.value })} /></label>
              <label><span className="fdas-label">Start Time</span><input type="time" className="fdas-input mt-1" value={form.startTime} onChange={e => setForm({ ...form, startTime: e.target.value })} /></label>
              <label><span className="fdas-label">End Time</span><input type="time" className="fdas-input mt-1" value={form.endTime} onChange={e => setForm({ ...form, endTime: e.target.value })} /></label>
              <label><span className="fdas-label">Status</span><select className="fdas-input mt-1" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}><option>Active</option><option>Inactive</option></select></label>
            </div>
      </FormDialog>

      <ConfirmDialog open={Boolean(statusDialog)} onClose={() => setStatusDialog(null)} onConfirm={() => toggleTiming(statusDialog)} title={statusDialog?.status === 'Active' ? 'Deactivate Time Window?' : 'Activate Time Window?'} description={statusDialog?.departmentName} confirmLabel={statusDialog?.status === 'Active' ? 'Deactivate' : 'Activate'} destructive={statusDialog?.status === 'Active'} busy={saving}>
        <p className="rounded-xl p-4 text-sm" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>{statusDialog?.status === 'Active' ? 'Attendance will no longer open under this schedule until the window is activated again.' : 'This schedule will become available for attendance sessions.'}</p>
      </ConfirmDialog>
    </section>
  )
}
