import { useState } from 'react'
import { DEPARTMENTS } from '../data/dummyData'
import Icon from './Icon'

/**
 * FilterBar — Search + filter controls for student/report pages
 *
 * Props:
 *   searchPlaceholder - Placeholder text for search input
 *   showDeptFilter    - Show department dropdown
 *   showClassFilter   - Show class/status filter
 *   departments       - Array of department names
 *   onSearch          - Callback(value)
 *   onDeptChange      - Callback(value)
 *   onStatusChange    - Callback(value)
 *   actionButton      - Optional JSX for right-side action button
 */
export default function FilterBar({
  searchPlaceholder = 'Search...',
  showDeptFilter = true,
  showStatusFilter = false,
  departments = DEPARTMENTS,
  onSearch,
  onDeptChange,
  onStatusChange,
  actionButton,
}) {
  const [search, setSearch] = useState('')

  const handleSearch = (e) => {
    setSearch(e.target.value)
    onSearch?.(e.target.value)
  }

  return (
    <div
      className="rounded-xl p-4 flex flex-col md:flex-row gap-3 items-start md:items-center justify-between"
      style={{ backgroundColor: '#FFF0E6', boxShadow: '0 4px 15px rgba(232,146,74,0.12)' }}
    >
      {/* Search */}
      <div className="relative w-full md:w-80">
        <Icon name="search" size={20} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: '#887369' }} />
        <input
          type="text"
          value={search}
          onChange={handleSearch}
          placeholder={searchPlaceholder}
          className="w-full pl-10 pr-4 py-2.5 rounded-lg border text-sm outline-none transition-all"
          style={{
            backgroundColor: '#ffffff',
            borderColor: '#dbc1b7',
            color: '#4A2B0F',
          }}
          onFocus={e => { e.target.style.borderColor = '#C4533A'; e.target.style.boxShadow = '0 0 0 2px rgba(196,83,58,0.1)' }}
          onBlur={e => { e.target.style.borderColor = '#dbc1b7'; e.target.style.boxShadow = 'none' }}
        />
      </div>

      {/* Filters + Action */}
      <div className="flex flex-wrap items-center gap-2">
        {showDeptFilter && (
          <select
            onChange={e => onDeptChange?.(e.target.value)}
            className="px-3 py-2.5 rounded-lg border text-sm outline-none cursor-pointer"
            style={{ backgroundColor: '#ffffff', borderColor: '#D4A017', color: '#4A2B0F' }}
          >
            <option value="">All Departments</option>
            {departments.map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        )}

        {showStatusFilter && (
          <select
            onChange={e => onStatusChange?.(e.target.value)}
            className="px-3 py-2.5 rounded-lg border text-sm outline-none cursor-pointer"
            style={{ backgroundColor: '#ffffff', borderColor: '#D4A017', color: '#4A2B0F' }}
          >
            <option value="">All Status</option>
            <option value="enrolled">Enrolled</option>
            <option value="not_enrolled">Not Enrolled</option>
          </select>
        )}

        {actionButton}
      </div>
    </div>
  )
}
