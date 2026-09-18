import Icon from './Icon'
import Badge from './ui/Badge'
import { EmptyState } from './ui/AsyncState'

/**
 * StudentTable — Reusable student list table
 *
 * Props:
 *   students      - Array of student objects
 *   actionsEnabled - Show edit/archive action buttons
 *   onEdit        - Callback (student) => void
 *   onView        - Callback (student) => void
 *   onStatusChange - Callback (student) => void
 *   onPermanentDelete - Callback (student) => void
 *   onRegisterFace - Callback (student) => void
 *   onRecover     - Callback (student) => void
 *   onDiagnose    - Callback (student) => void
 *   showEnrollment - Show face enrollment status column
 */
export default function StudentTable({
  students = [],
  actionsEnabled = false,
  onEdit,
  onView,
  onStatusChange,
  onPermanentDelete,
  onRegisterFace,
  onRecover,
  onDiagnose,
  showEnrollment = true,
  showStatus = true,
}) {
  if (students.length === 0) {
    return (
      <EmptyState title="No students found" description="Try adjusting your search or status view." icon="group_off" />
    )
  }

  return (
    <div className="fdas-table-wrap">
      <table className={`fdas-table ${actionsEnabled ? 'min-w-[1040px]' : ''}`}>
        <thead>
          <tr
            className="text-xs font-bold uppercase tracking-wider border-b-2"
            style={{ borderColor: '#C4533A', color: '#C4533A', backgroundColor: '#fff1eb' }}
          >
            <th className="whitespace-nowrap">Name</th>
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
                    <Badge icon="check_circle">Face Ready</Badge>
                  ) : student.hasEncodedFaceTemplates ? (
                    <Badge tone="warning" icon="hourglass_empty">Face Registration Incomplete</Badge>
                  ) : (
                    <Badge tone="warning" icon="radio_button_unchecked">Pending Face Registration</Badge>
                  )}
                </td>
              )}
              {showStatus && (
                <td className="py-3 px-4">
                  <Badge>{student.status === 'Active' ? 'Active' : 'Inactive'}</Badge>
                </td>
              )}
              {actionsEnabled && (
                <td className="py-3 px-4 text-right">
                  <div className="fdas-table-actions">
                    {onView && (
                      <button
                        onClick={() => onView(student)}
                        className="fdas-icon-button fdas-icon-button-sm"
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
                        className="fdas-icon-button fdas-icon-button-sm hover:bg-teal-50"
                        style={{ color: '#0f766e' }}
                        title="Independent deep recognition diagnostic"
                        aria-label={`Independent deep recognition diagnostic for ${student.name}`}
                      >
                        <Icon name="biotech" size={18} />
                      </button>
                    )}
                    {onRegisterFace && !student.enrolled && (
                      <button
                        onClick={() => onRegisterFace(student)}
                        className="fdas-icon-button fdas-icon-button-sm hover:bg-emerald-50"
                        style={{ color: '#087a68' }}
                        title="Register face"
                        aria-label={`Register face for ${student.name}`}
                      >
                        <Icon name="add_a_photo" size={18} />
                      </button>
                    )}
                    {onRecover && student.enrolled && (
                      <button
                        onClick={() => onRecover(student)}
                        className="fdas-icon-button fdas-icon-button-sm hover:bg-amber-50"
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
                        className="fdas-icon-button fdas-icon-button-sm"
                        style={{ color: '#C4533A' }}
                        title="Edit student"
                        aria-label={`Edit ${student.name}`}
                      >
                        <Icon name="edit" size={18} />
                      </button>
                    )}
                    <button
                      onClick={() => onStatusChange?.(student)}
                      className={`fdas-icon-button fdas-icon-button-sm ${student.status === 'Active' ? 'hover:bg-red-50' : 'hover:bg-emerald-50'}`}
                      style={{ color: student.status === 'Active' ? '#ba1a1a' : '#065f46' }}
                      title={student.status === 'Active' ? 'Deactivate student' : 'Reactivate student'}
                      aria-label={`${student.status === 'Active' ? 'Deactivate' : 'Reactivate'} ${student.name}`}
                    >
                      <Icon name={student.status === 'Active' ? 'archive' : 'restore'} size={18} />
                    </button>
                    {onPermanentDelete && (
                      <button
                        onClick={() => onPermanentDelete(student)}
                        className="fdas-icon-button fdas-icon-button-sm hover:bg-red-50"
                        style={{ color: '#ba1a1a' }}
                        title="Delete student"
                        aria-label={`Delete ${student.name}`}
                      >
                        <Icon name="delete" size={18} />
                      </button>
                    )}
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
