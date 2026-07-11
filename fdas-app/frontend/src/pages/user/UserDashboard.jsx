import { useEffect, useState } from 'react'
import AttendanceChart from '../../components/AttendanceChart'
import AttendanceLogSidebar from '../../components/AttendanceLogSidebar'
import StatsCard from '../../components/StatsCard'
import { ANALYTICS_WEEKLY, LIVE_LOG } from '../../data/dummyData'
import { studentsApi } from '../../api/studentsApi'
import { useAuth } from '../../context/useAuth'

export default function UserDashboard() {
  const { assignedDepartmentName, hasAllDepartmentsAccess } = useAuth()
  const [studentCount, setStudentCount] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadStudents() {
      try {
        const students = await studentsApi.list()
        setStudentCount(students.length)
      } finally {
        setLoading(false)
      }
    }
    loadStudents()
  }, [])

  return (
    <section className="fdas-page space-y-6 animate-fade-in-up">
      <div>
        <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Operator Overview</p>
        <h1 className="text-4xl font-black" style={{ color: '#4A2B0F' }}>Department Dashboard</h1>
        <p className="text-sm mt-2" style={{ color: '#55433b' }}>{hasAllDepartmentsAccess() ? 'All departments access' : assignedDepartmentName}</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatsCard title="Visible Students" value={loading ? '...' : studentCount} icon="groups" />
        <StatsCard title="Present Today" value="Demo" icon="task_alt" iconColor="#D4A017" />
        <StatsCard title="Absent Today" value="Demo" icon="event_busy" iconColor="#C4533A" />
        <StatsCard title="Attendance Rate" value="Demo" icon="trending_up" iconColor="#E8924A" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-5 min-w-0">
        <AttendanceChart data={ANALYTICS_WEEKLY} type="line" title="Department Attendance" />
        <AttendanceLogSidebar records={LIVE_LOG.slice(0, 5)} title="Recent Marks" />
      </div>
    </section>
  )
}
