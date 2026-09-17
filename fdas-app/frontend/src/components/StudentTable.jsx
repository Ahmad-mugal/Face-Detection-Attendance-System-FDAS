import Icon from './Icon'

/**
 * StudentTable — Reusable student list table
 *
 * Props:
 *   students      - Array of student objects
 *   actionsEnabled - Show edit/archive action buttons
 *   onEdit        - Callback (student) => void
 *   onView        - Callback (student) => void
 *   onDelete      - Callback (student) => void
 *   onRecover     - Callback (student) => void
 *   onDiagnose    - Callback (student) => void
 *   showEnrollment - Show face enrollment status column
 */
export default function StudentTable({
  students = [],
  actionsEnabled = false,
  onEdit,
  onView,
  onDelete,
  onRecover,
  onDiagnose,
  showEnrollment = true,
  showStatus = true,
}) {
  if (students.length === 0) {
    return (
      <div className="text-center py-16" style={{ color: '#887369' }}>
        <Icon name="group_off" size={48} className="block mx-auto mb-3" style={{ color: '#dbc1b7' }} />
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
            {showStatus && <th className="py-3 px-4 whitespace-nowrap">Status</th>}
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
                      <Icon name="check_circle" size={12} />
                      Enrolled
                    </span>
                  ) : (
                    <span
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold"
                      style={{ backgroundColor: '#ffdad6', color: '#93000a' }}
                    >
                      <Icon name="radio_button_unchecked" size={12} />
                      Not Enrolled
                    </span>
                  )}
                </td>
              )}
              {showStatus && (
                <td className="py-3 px-4">
                  <span
                    className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold"
                    style={student.status === 'Active'
                      ? { backgroundColor: '#d1fae5', color: '#065f46' }
                      : { backgroundColor: '#f0dfd8', color: '#6f3b20' }}
                  >
                    {student.status === 'Active' ? 'Active' : 'Inactive'}
                  </span>
                </td>
              )}
              {actionsEnabled && (
                <td className="py-3 px-4 text-right">
                  <div className="flex items-center gap-1 justify-end">
                    {onView && (
                      <button
                        onClick={() => onView(student)}
                        className="p-1.5 rounded-lg transition-colors hover:bg-orange-100"
                        style={{ color: '#795900' }}
                        title="View student"
                        aria-label={`View ${student.name}`}
                      >
                        <Icon name="visibility" size={18} />
                      </button>
                    )}
                    {onDiagnose && student.status === 'Active' && (
                      <button
                        onClick={() => onDiagnose(student)}
                        className="p-1.5 rounded-lg transition-colors hover:bg-teal-50"
                        style={{ color: '#0f766e' }}
                        title="Independent deep recognition diagnostic"
                        aria-label={`Independent deep recognition diagnostic for ${student.name}`}
                      >
                        <Icon name="biotech" size={18} />
                      </button>
                    )}
                    {onRecover && (
                      <button
                        onClick={() => onRecover(student)}
                        className="p-1.5 rounded-lg transition-colors hover:bg-amber-50"
                        style={{ color: '#934619' }}
                        title="Deep enrollment recovery"
                        aria-label={`Deep enrollment recovery for ${student.name}`}
                      >
                        <Icon name="face_retouching_natural" size={18} />
                      </button>
                    )}
                    {onEdit && (
                      <button
                        onClick={() => onEdit(student)}
                        className="p-1.5 rounded-lg transition-colors hover:bg-orange-100"
                        style={{ color: '#C4533A' }}
                        title="Edit student"
                        aria-label={`Edit ${student.name}`}
                      >
                        <Icon name="edit" size={18} />
                      </button>
                    )}
                    <button
                      onClick={() => onDelete?.(student)}
                      className={`p-1.5 rounded-lg transition-colors ${student.status === 'Active' ? 'hover:bg-red-50' : 'hover:bg-emerald-50'}`}
                      style={{ color: student.status === 'Active' ? '#ba1a1a' : '#065f46' }}
                      title={student.status === 'Active' ? 'Deactivate student' : 'Reactivate student'}
                      aria-label={`${student.status === 'Active' ? 'Deactivate' : 'Reactivate'} ${student.name}`}
                    >
                      <Icon name={student.status === 'Active' ? 'archive' : 'restore'} size={18} />
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
