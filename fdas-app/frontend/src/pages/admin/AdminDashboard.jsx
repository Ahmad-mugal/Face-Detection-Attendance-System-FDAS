import { useEffect, useState } from 'react'
import AttendanceChart from '../../components/AttendanceChart'
import AttendanceLogSidebar from '../../components/AttendanceLogSidebar'
import StatsCard from '../../components/StatsCard'
import { ANALYTICS_WEEKLY, LIVE_LOG, SESSIONS } from '../../data/dummyData'
import { studentsApi } from '../../api/studentsApi'
import { adminUsersApi } from '../../api/adminUsersApi'
import { classesApi } from '../../api/classesApi'
import Icon from '../../components/Icon'

export default function AdminDashboard() {
  const activeSession = SESSIONS.find(session => session.status === 'active')
  const [counts, setCounts] = useState({ students: 0, users: 0, classes: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadCounts() {
      try {
        const [students, users, classes] = await Promise.all([
          studentsApi.list(),
          adminUsersApi.listUsers(),
          classesApi.list(),
        ])
        setCounts({ students: students.length, users: users.length, classes: classes.length })
      } finally {
        setLoading(false)
      }
    }
    loadCounts()
  }, [])

  return (
    <section className="fdas-page space-y-6 animate-fade-in-up">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Admin Overview</p>
          <h1 className="text-4xl font-black mt-1" style={{ color: '#4A2B0F' }}>FDAS Dashboard</h1>
          <p className="text-sm mt-2" style={{ color: '#55433b' }}>Backend-connected counts with dummy attendance charts until attendance APIs are added.</p>
        </div>
        <div className="rounded-xl px-4 py-3 border" style={{ backgroundColor: '#fff8f6', borderColor: '#dbc1b7', color: '#55433b' }}>
          <Icon name="bolt" size={18} className="mr-1" style={{ color: '#D4A017' }} />
          Active session: <strong style={{ color: '#934619' }}>{activeSession?.className || 'None'}</strong>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatsCard title="Total Students" value={loading ? '...' : counts.students} icon="groups" borderColor="#C4533A" filled />
        <StatsCard title="Users" value={loading ? '...' : counts.users} icon="manage_accounts" iconColor="#D4A017" borderColor="#D4A017" filled />
        <StatsCard title="Classes" value={loading ? '...' : counts.classes} icon="school" iconColor="#C4533A" borderColor="#C4533A" />
        <StatsCard title="Attendance Accuracy" value="Demo" icon="verified" iconColor="#E8924A" borderColor="#E8924A" filled />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-5 min-w-0">
        <AttendanceChart data={ANALYTICS_WEEKLY} title="Weekly Attendance Trend" />
        <AttendanceLogSidebar records={LIVE_LOG} title="Live Attendance Log" />
      </div>
    </section>
  )
}
