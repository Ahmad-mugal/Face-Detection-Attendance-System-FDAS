/**
 * StudentTable — Reusable student list table
 *
 * Props:
 *   students      - Array of student objects
 *   actionsEnabled - Show edit/archive action buttons
 *   onEdit        - Callback (student) => void
 *   onDelete      - Callback (student) => void
 *   showEnrollment - Show face enrollment status column
 */
export default function StudentTable({
  students = [],
  actionsEnabled = false,
  onEdit,
  onDelete,
  showEnrollment = true,
}) {
  if (students.length === 0) {
    return (
      <div className="text-center py-16" style={{ color: '#887369' }}>
        <span className="material-symbols-outlined text-[48px] block mb-3" style={{ color: '#dbc1b7' }}>group_off</span>
        <p className="font-semibold">No students found</p>
        <p className="text-sm mt-1">Try adjusting your filters</p>
      </div>
    )
  }

  return (
    <div className="fdas-table-wrap">
      <table className="fdas-table">
        <thead>
          <tr
            className="text-xs font-bold uppercase tracking-wider border-b-2"
            style={{ borderColor: '#C4533A', color: '#C4533A', backgroundColor: '#fff1eb' }}
          >
            <th className="py-3 px-4 whitespace-nowrap">Name</th>
            <th className="py-3 px-4 whitespace-nowrap">Roll No.</th>
            <th className="py-3 px-4 whitespace-nowrap">Class</th>
            <th className="py-3 px-4 whitespace-nowrap">Department</th>
            {showEnrollment && <th className="py-3 px-4 whitespace-nowrap">Face Enrolled</th>}
            {actionsEnabled && <th className="py-3 px-4 whitespace-nowrap text-right">Actions</th>}
          </tr>
        </thead>
        <tbody>
          {students.map((student, idx) => (
            <tr
              key={student.id}
              className="border-b transition-colors hover:bg-orange-50/40"
              style={{ borderColor: '#f0dfd8', backgroundColor: idx % 2 === 0 ? '#FFF0E6' : '#ffffff' }}
            >
              <td className="py-3 px-4">
                <div className="flex items-center gap-3">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                    style={{ backgroundColor: '#C4533A' }}
                  >
                    {student.name.charAt(0)}
                  </div>
                  <div>
                    <div className="font-semibold text-sm" style={{ color: '#4A2B0F' }}>{student.name}</div>
                    <div className="text-xs" style={{ color: '#887369' }}>{student.email}</div>
                  </div>
                </div>
              </td>
              <td className="py-3 px-4">
                <span className="text-sm font-mono font-semibold" style={{ color: '#934619' }}>{student.rollNumber}</span>
              </td>
              <td className="py-3 px-4 text-sm" style={{ color: '#4A2B0F' }}>{student.className}</td>
              <td className="py-3 px-4 text-sm" style={{ color: '#55433b' }}>{student.department}</td>
              {showEnrollment && (
                <td className="py-3 px-4">
                  {student.enrolled ? (
                    <span
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold"
                      style={{ backgroundColor: '#d1fae5', color: '#065f46' }}
                    >
                      <span className="material-symbols-outlined text-[12px] filled">check_circle</span>
                      Enrolled
                    </span>
                  ) : (
                    <span
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold"
                      style={{ backgroundColor: '#ffdad6', color: '#93000a' }}
                    >
                      <span className="material-symbols-outlined text-[12px]">radio_button_unchecked</span>
                      Not Enrolled
                    </span>
                  )}
                </td>
              )}
              {actionsEnabled && (
                <td className="py-3 px-4 text-right">
                  <div className="flex items-center gap-1 justify-end">
                    <button
                      onClick={() => onEdit?.(student)}
                      className="p-1.5 rounded-lg transition-colors hover:bg-orange-100"
                      style={{ color: '#C4533A' }}
                      title="Edit student"
                    >
                      <span className="material-symbols-outlined text-[18px]">edit</span>
                    </button>
                    <button
                      onClick={() => onDelete?.(student)}
                      className="p-1.5 rounded-lg transition-colors hover:bg-red-50"
                      style={{ color: '#ba1a1a' }}
                      title="Archive student"
                    >
                      <span className="material-symbols-outlined text-[18px]">archive</span>
                    </button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
