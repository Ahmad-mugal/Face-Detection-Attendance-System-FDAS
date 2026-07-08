import AttendanceChart from '../../components/AttendanceChart'
import AttendanceLogSidebar from '../../components/AttendanceLogSidebar'
import StatsCard from '../../components/StatsCard'
import { ANALYTICS_WEEKLY, LIVE_LOG, USER_STATS } from '../../data/dummyData'

export default function UserDashboard() {
  return (
    <section className="fdas-page space-y-6 animate-fade-in-up">
      <div>
        <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Operator Overview</p>
        <h1 className="text-4xl font-black" style={{ color: '#4A2B0F' }}>Department Dashboard</h1>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatsCard title="Dept Students" value={USER_STATS.totalStudentsInDept} icon="groups" />
        <StatsCard title="Present Today" value={USER_STATS.presentToday} icon="task_alt" iconColor="#D4A017" />
        <StatsCard title="Absent Today" value={USER_STATS.absentToday} icon="event_busy" iconColor="#C4533A" />
        <StatsCard title="Attendance Rate" value={`${USER_STATS.attendanceRate}%`} icon="trending_up" iconColor="#E8924A" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-5 min-w-0">
        <AttendanceChart data={ANALYTICS_WEEKLY} type="line" title="Department Attendance" />
        <AttendanceLogSidebar records={LIVE_LOG.slice(0, 5)} title="Recent Marks" />
      </div>
    </section>
  )
}
