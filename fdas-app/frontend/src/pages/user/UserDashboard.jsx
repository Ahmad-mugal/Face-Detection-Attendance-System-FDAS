import { useEffect, useState } from 'react'
import AttendanceChart from '../../components/AttendanceChart'
import AttendanceLogSidebar from '../../components/AttendanceLogSidebar'
import StatsCard from '../../components/StatsCard'
import { dashboardApi } from '../../api/dashboardApi'
import { getApiError } from '../../api/client'
import { useAuth } from '../../context/useAuth'

export default function UserDashboard() {
  const { assignedDepartmentName, hasAllDepartmentsAccess } = useAuth()
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
      <div>
        <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Operator Overview</p>
        <h1 className="text-4xl font-black" style={{ color: '#4A2B0F' }}>Department Dashboard</h1>
        <p className="text-sm mt-2" style={{ color: '#55433b' }}>{hasAllDepartmentsAccess() ? 'All departments access' : (assignedDepartmentName || 'Department User')}</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatsCard title="Visible Students" value={loading ? '...' : (summary?.totalStudents ?? 0)} icon="groups" />
        <StatsCard title="Present Today" value={loading ? '...' : (summary?.presentToday ?? 0)} icon="task_alt" iconColor="#D4A017" />
        <StatsCard title="Not Marked Today" value={loading ? '...' : (summary?.notMarkedToday ?? 0)} icon="event_busy" iconColor="#C4533A" />
        <StatsCard title="Attendance Rate" value={loading ? '...' : `${summary?.attendanceRate ?? 0}%`} icon="trending_up" iconColor="#E8924A" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-5 min-w-0">
        <AttendanceChart data={summary?.weeklyChart || []} type="line" title="Department Attendance" />
        <AttendanceLogSidebar records={(summary?.recentRecords || []).slice(0, 5)} title="Recent Marks" actionPath="/user/reports" actionLabel="View Reports" />
      </div>
    </section>
  )
}
