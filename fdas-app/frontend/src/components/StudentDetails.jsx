export default function StudentDetails({ student }) {
  if (!student) return null
  const rows = [
    ['Name', student.name],
    ['Email', student.email || 'Not provided'],
    ['Roll No.', student.rollNumber],
    ['Class', student.className || 'Not assigned'],
    ['Department', student.department || 'Not assigned'],
    ['Face enrollment', student.enrolled ? 'Enrolled' : 'Not enrolled'],
    ['Status', student.status === 'Active' ? 'Active' : 'Inactive'],
  ]
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-xl border p-3" style={{ borderColor: '#f0dfd8', backgroundColor: '#fff' }}>
          <dt className="fdas-label">{label}</dt>
          <dd className="mt-1 font-semibold break-words" style={{ color: '#4A2B0F' }}>{value}</dd>
        </div>
      ))}
    </dl>
  )
}
