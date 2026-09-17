import { useState } from 'react'
import Icon from '../../components/Icon'
import Toast from '../../components/ui/Toast'
import { loadPreferences, savePreferences } from '../../utils/preferences'
import PageHeader from '../../components/ui/PageHeader'

function Toggle({ checked, onChange, label, description }) {
  return (
    <label className="flex items-start justify-between gap-4 rounded-xl border p-4 cursor-pointer" style={{ borderColor: '#f0dfd8', backgroundColor: '#fffdfb' }}>
      <span><span className="block font-bold" style={{ color: '#4A2B0F' }}>{label}</span><span className="block mt-1 text-sm" style={{ color: '#6f5b52' }}>{description}</span></span>
      <input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} className="mt-1 h-5 w-5 accent-[#C4533A] shrink-0" />
    </label>
  )
}

export default function AccountPreferences() {
  const [preferences, setPreferences] = useState(loadPreferences)
  const [saved, setSaved] = useState('')

  const update = next => {
    setPreferences(next)
    savePreferences(next)
    setSaved('Preferences saved on this device.')
  }

  return (
    <section className="fdas-page space-y-6 animate-fade-in-up">
      <Toast message={saved} onDismiss={() => setSaved('')} />
      <PageHeader eyebrow="Your Experience" title="Account Preferences" description="These interface-only preferences are stored locally in this browser. They do not change account permissions or attendance rules." />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <article className="p-5 sm:p-6 fdas-card">
          <div className="flex items-center gap-3"><Icon name="table_rows" size={22} style={{ color: '#C4533A' }} /><h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Table Density</h2></div>
          <p className="mt-2 text-sm" style={{ color: '#6f5b52' }}>Choose the spacing used by student, user, and attendance tables.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-5" role="radiogroup" aria-label="Table density">
            {['comfortable', 'compact'].map(value => (
              <label key={value} className="rounded-xl border p-4 cursor-pointer" style={{ borderColor: preferences.tableDensity === value ? '#C4533A' : '#dbc1b7', backgroundColor: preferences.tableDensity === value ? '#fff1eb' : '#fff' }}>
                <input type="radio" name="tableDensity" value={value} checked={preferences.tableDensity === value} onChange={() => update({ ...preferences, tableDensity: value })} className="accent-[#C4533A]" />
                <span className="ml-2 font-bold capitalize" style={{ color: '#4A2B0F' }}>{value}</span>
              </label>
            ))}
          </div>
        </article>

        <article className="p-5 sm:p-6 fdas-card">
          <div className="flex items-center gap-3"><Icon name="event_available" size={22} style={{ color: '#C4533A' }} /><h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Attendance UI</h2></div>
          <div className="mt-5">
            <Toggle checked={preferences.autoRefreshAttendance} onChange={checked => update({ ...preferences, autoRefreshAttendance: checked })} label="Automatically refresh session records" description="Refresh the current attendance list periodically while a session is active." />
          </div>
        </article>

        <article className="p-5 sm:p-6 fdas-card lg:col-span-2">
          <div className="flex items-center gap-3"><Icon name="accessibility_new" size={22} style={{ color: '#C4533A' }} /><h2 className="text-xl font-black" style={{ color: '#4A2B0F' }}>Accessibility</h2></div>
          <div className="mt-5 max-w-2xl">
            <Toggle checked={preferences.reducedMotion} onChange={checked => update({ ...preferences, reducedMotion: checked })} label="Reduce interface motion" description="Disable non-essential page, pulse, and scanning animations on this device." />
          </div>
        </article>
      </div>
    </section>
  )
}
