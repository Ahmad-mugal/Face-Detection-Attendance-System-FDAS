import AttendanceChart from '../../components/AttendanceChart'
import AttendanceLogSidebar from '../../components/AttendanceLogSidebar'
import StatsCard from '../../components/StatsCard'
import { ADMIN_STATS, ANALYTICS_WEEKLY, LIVE_LOG, SESSIONS } from '../../data/dummyData'

export default function AdminDashboard() {
  const activeSession = SESSIONS.find(session => session.status === 'active')

  return (
    <section className="fdas-page space-y-6 animate-fade-in-up">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Admin Overview</p>
          <h1 className="text-4xl font-black mt-1" style={{ color: '#4A2B0F' }}>FDAS Dashboard</h1>
          <p className="text-sm mt-2" style={{ color: '#55433b' }}>Static Phase 1 shell using Stitch-style dummy attendance data.</p>
        </div>
        <div className="rounded-xl px-4 py-3 border" style={{ backgroundColor: '#fff8f6', borderColor: '#dbc1b7', color: '#55433b' }}>
          <span className="material-symbols-outlined text-[18px] align-middle mr-1" style={{ color: '#D4A017' }}>bolt</span>
          Active session: <strong style={{ color: '#934619' }}>{activeSession?.className || 'None'}</strong>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatsCard title="Total Students" value={ADMIN_STATS.totalStudents} icon="groups" borderColor="#C4533A" filled />
        <StatsCard title="Present Today" value={ADMIN_STATS.presentToday} subtitle="89%" icon="task_alt" iconColor="#D4A017" borderColor="#D4A017" filled />
        <StatsCard title="Absent Today" value={ADMIN_STATS.absentToday} subtitle="11%" icon="event_busy" iconColor="#C4533A" borderColor="#C4533A" />
        <StatsCard title="Attendance Accuracy" value={`${ADMIN_STATS.recognitionAccuracy}%`} icon="verified" iconColor="#E8924A" borderColor="#E8924A" filled />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-5 min-w-0">
        <AttendanceChart data={ANALYTICS_WEEKLY} title="Weekly Attendance Trend" />
        <AttendanceLogSidebar records={LIVE_LOG} title="Live Attendance Log" />
      </div>
    </section>
  )
}
