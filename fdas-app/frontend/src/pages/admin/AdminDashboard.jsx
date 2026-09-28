import { useEffect, useState } from 'react'
import AttendanceChart from '../../components/AttendanceChart'
import AttendanceLogSidebar from '../../components/AttendanceLogSidebar'
import StatsCard from '../../components/StatsCard'
import Icon from '../../components/Icon'
import { dashboardApi } from '../../api/dashboardApi'
import { getApiError } from '../../api/client'
import PageHeader from '../../components/ui/PageHeader'

export default function AdminDashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadDashboardData() {
      try {
        setError('')
        const data = await dashboardApi.getSummary()
        setSummary(data)
      } catch (err) {
        setError(getApiError(err, 'Unable to load dashboard data.'))
      } finally {
        setLoading(false)
      }
    }
    loadDashboardData()
  }, [])

  return (
    <section className="fdas-page space-y-6 animate-fade-in-up">
      {error && <div role="alert" className="rounded-xl border px-4 py-3 text-sm font-semibold" style={{ backgroundColor: '#ffdad6', borderColor: '#f2b8b5', color: '#93000a' }}>{error}</div>}
      <PageHeader
        eyebrow="Admin Overview"
        title="FDAS Dashboard"
        description="Real-time overview of enrolled students, registered users, active classes, and attendance reports."
        actions={<div className="fdas-card px-4 py-2.5 text-sm" style={{ color: '#55433b' }}>
          <Icon name="bolt" size={18} className="mr-1" style={{ color: '#D4A017' }} />
          Active session: <strong style={{ color: '#934619' }}>{summary?.activeSessionName || 'None'}</strong>
        </div>}
      />

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

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-5 min-w-0 items-start">
        <AttendanceChart data={summary?.weeklyChart || []} title="Weekly Attendance Trend" height={360} />
        <AttendanceLogSidebar records={summary?.recentRecords || []} title="Live Attendance Log" actionPath="/admin/analytics" actionLabel="Open Reports" />
      </div>
    </section>
  )
}
