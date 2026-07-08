import AttendanceChart from '../../components/AttendanceChart'
import CSVExportButton from '../../components/CSVExportButton'
import StatsCard from '../../components/StatsCard'
import { ANALYTICS_MONTHLY, ANALYTICS_WEEKLY, ADMIN_STATS, ATTENDANCE_RECORDS, CLASSES } from '../../data/dummyData'

export default function AdminAnalytics() {
  const pieData = [
    { name: 'Present', value: ADMIN_STATS.presentToday, color: '#D4A017' },
    { name: 'Absent', value: ADMIN_STATS.absentToday, color: '#C4533A' },
  ]

  return (
    <section className="fdas-page space-y-5 animate-fade-in-up">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>Reports</p>
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Attendance Analytics</h1>
        </div>
        <CSVExportButton data={ANALYTICS_WEEKLY} filename="fdas_analytics.csv" />
      </div>

      <div className="rounded-xl p-4 fdas-card">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
          <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Date From</span><input type="date" className="mt-1 w-full rounded-lg border px-3 py-2.5" style={{ borderColor: '#dbc1b7' }} /></label>
          <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Date To</span><input type="date" className="mt-1 w-full rounded-lg border px-3 py-2.5" style={{ borderColor: '#dbc1b7' }} /></label>
          <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Class</span><select className="mt-1 w-full rounded-lg border px-3 py-2.5" style={{ borderColor: '#dbc1b7' }}><option>All Classes</option>{CLASSES.filter(item => !item.isArchived).map(item => <option key={item.id}>{item.name}</option>)}</select></label>
          <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Student</span><input className="mt-1 w-full rounded-lg border px-3 py-2.5" style={{ borderColor: '#dbc1b7' }} placeholder="Search student" /></label>
          <label><span className="text-xs font-bold uppercase" style={{ color: '#55433b' }}>Status</span><select className="mt-1 w-full rounded-lg border px-3 py-2.5" style={{ borderColor: '#dbc1b7' }}><option>All Status</option><option>Present</option><option>Absent</option><option>Late</option></select></label>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatsCard title="Attendance Rate" value="89%" icon="trending_up" iconColor="#D4A017" />
        <StatsCard title="Classes Tracked" value={ADMIN_STATS.totalClasses} icon="school" />
        <StatsCard title="Active Operators" value={ADMIN_STATS.activeOperators} icon="manage_accounts" iconColor="#E8924A" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <AttendanceChart data={ANALYTICS_WEEKLY} type="line" title="This Week" />
        <AttendanceChart data={ANALYTICS_MONTHLY} title="Monthly Comparison" />
        <AttendanceChart data={pieData} type="pie" title="Today Summary" />
      </div>

      <div className="rounded-xl fdas-card overflow-hidden">
        <div className="fdas-table-wrap">
          <table className="fdas-table">
            <thead className="text-xs uppercase" style={{ color: '#C4533A', backgroundColor: '#fff1eb' }}>
              <tr><th className="p-4">Student</th><th className="p-4">Roll No.</th><th className="p-4">Department</th><th className="p-4">Status</th><th className="p-4">Confidence</th></tr>
            </thead>
            <tbody>
              {ATTENDANCE_RECORDS.map(record => (
                <tr key={record.id} className="border-t" style={{ borderColor: '#f0dfd8' }}>
                  <td className="p-4 font-bold" style={{ color: '#4A2B0F' }}>{record.studentName}</td>
                  <td className="p-4 font-mono text-sm">{record.rollNumber}</td>
                  <td className="p-4">{record.departmentId}</td>
                  <td className="p-4 capitalize">{record.status}</td>
                  <td className="p-4">{Math.round(record.recognitionConfidence * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
