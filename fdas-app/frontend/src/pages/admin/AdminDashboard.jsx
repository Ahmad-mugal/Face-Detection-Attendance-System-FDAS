import { useEffect, useState } from 'react'
import AttendanceChart from '../../components/AttendanceChart'
import AttendanceLogSidebar from '../../components/AttendanceLogSidebar'
import StatsCard from '../../components/StatsCard'
import Icon from '../../components/Icon'
import { dashboardApi } from '../../api/dashboardApi'

export default function AdminDashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadDashboardData() {
      try {
        const data = await dashboardApi.getSummary()
        setSummary(data)
      } catch (err) {
        console.error('Failed to load admin dashboard data:', err)
      } finally {
        setLoading(false)
      }
    }
    loadDashboardData()
  }, [])

  return (
    <section className="fdas-page space-y-6 animate-fade-in-up">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Admin Overview</p>
          <h1 className="text-4xl font-black mt-1" style={{ color: '#4A2B0F' }}>FDAS Dashboard</h1>
          <p className="text-sm mt-2" style={{ color: '#55433b' }}>Real-time overview of enrolled students, registered users, active classes, and attendance analytics.</p>
        </div>
        <div className="rounded-xl px-4 py-3 border" style={{ backgroundColor: '#fff8f6', borderColor: '#dbc1b7', color: '#55433b' }}>
          <Icon name="bolt" size={18} className="mr-1" style={{ color: '#D4A017' }} />
          Active session: <strong style={{ color: '#934619' }}>{summary?.activeSessionName || 'None'}</strong>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatsCard
          title="Total Students"
          value={loading ? '...' : (summary?.totalStudents ?? 0)}
          icon="groups"
          borderColor="#C4533A"
          filled
        />
        <StatsCard
          title="Present Today"
          value={loading ? '...' : (summary?.presentToday ?? 0)}
          subtitle={summary ? `Users: ${summary.totalUsers ?? 0}` : undefined}
          icon="task_alt"
          iconColor="#D4A017"
          borderColor="#D4A017"
          filled
        />
        <StatsCard
          title="Classes"
          value={loading ? '...' : (summary?.totalClasses ?? 0)}
          subtitle={summary?.activeSessionCount ? `${summary.activeSessionCount} Active Session` : undefined}
          icon="school"
          iconColor="#C4533A"
          borderColor="#C4533A"
        />
        <StatsCard
          title="Attendance Rate"
          value={loading ? '...' : `${summary?.attendanceRate ?? 0}%`}
          icon="verified"
          iconColor="#E8924A"
          borderColor="#E8924A"
          filled
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-5 min-w-0">
        <AttendanceChart data={summary?.weeklyChart || []} title="Weekly Attendance Trend" />
        <AttendanceLogSidebar records={summary?.recentRecords || []} title="Live Attendance Log" />
      </div>
    </section>
  )
}
