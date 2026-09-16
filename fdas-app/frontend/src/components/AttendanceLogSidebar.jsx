import Icon from './Icon'
import { Link } from 'react-router-dom'

/**
 * AttendanceLogSidebar — Live scrollable attendance log
 *
 * Props:
 *   records - Array of { id, studentName, rollNumber, markedAt, confidence }
 *   title   - Sidebar title
 */
export default function AttendanceLogSidebar({ records = [], title = "Today's Log", actionPath, actionLabel = 'Open Analytics' }) {
  return (
    <div
      className="rounded-xl border-t-[3px] flex flex-col overflow-hidden"
      style={{
        backgroundColor: '#FFF0E6',
        borderColor: '#D4A017',
        boxShadow: '0 4px 20px rgba(232,146,74,0.15)',
        minHeight: 400,
        maxHeight: 600,
      }}
    >
      {/* Header */}
      <div
        className="px-5 py-4 flex items-center justify-between border-b"
        style={{ borderColor: 'rgba(232,146,74,0.2)', backgroundColor: 'rgba(255,255,255,0.5)' }}
      >
        <h3 className="font-bold text-base" style={{ color: '#C4533A' }}>{title}</h3>
        <span
          className="text-xs font-bold px-3 py-1 rounded-full"
          style={{ backgroundColor: 'rgba(212,160,23,0.15)', color: '#795900' }}
        >
          {records.length} Present
        </span>
      </div>

      {/* Scrollable log list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {records.length === 0 ? (
          <div className="text-center py-12" style={{ color: '#887369' }}>
            <Icon name="hourglass_empty" size={40} className="block mx-auto mb-2" style={{ color: '#dbc1b7' }} />
            <p className="text-sm font-medium">Waiting for students...</p>
          </div>
        ) : (
          records.map((record, idx) => (
            <div
              key={record.id}
              className="flex items-center justify-between px-3 py-2.5 rounded-lg transition-colors hover:bg-white/60 animate-fade-in-up"
              style={{ backgroundColor: idx % 2 === 0 ? '#FFF0E6' : '#FAF4EC' }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: '#D4A017' }}
                />
                <div>
                  <div className="text-sm font-bold" style={{ color: '#4A2B0F' }}>{record.studentName}</div>
                  <div className="text-[10px] font-mono" style={{ color: '#887369' }}>{record.rollNumber}</div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs font-bold" style={{ color: '#E8924A' }}>{record.markedAt}</div>
                {record.confidence && (
                  <div className="text-[10px]" style={{ color: '#887369' }}>
                    {Math.round(record.confidence * 100)}% match
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div
        className="px-5 py-3 border-t text-center"
        style={{ borderColor: 'rgba(232,146,74,0.15)', backgroundColor: 'rgba(255,255,255,0.5)' }}
      >
        <Link
          to={actionPath}
          className="text-sm font-semibold flex items-center justify-center gap-1 w-full transition-colors"
          style={{ color: '#C4533A' }}
        >
          {actionLabel}
          <Icon name="arrow_forward" size={16} />
        </Link>
      </div>
    </div>
  )
}
