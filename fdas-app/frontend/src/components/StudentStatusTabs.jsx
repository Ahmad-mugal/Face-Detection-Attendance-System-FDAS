export default function StudentStatusTabs({ activeView, activeCount, inactiveCount, onChange }) {
  const tabs = [
    { id: 'active', label: 'Active Students', count: activeCount },
    { id: 'inactive', label: 'Inactive Students', count: inactiveCount },
  ]

  return (
    <div className="fdas-card rounded-xl p-1.5 inline-flex max-w-full overflow-x-auto" role="tablist" aria-label="Student status">
      {tabs.map(tab => {
        const selected = activeView === tab.id
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.id)}
            className="min-h-10 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-extrabold transition-colors"
            style={selected
              ? { backgroundColor: '#C4533A', color: '#fff' }
              : { backgroundColor: 'transparent', color: '#55433b' }}
          >
            {tab.label} <span aria-label={`${tab.count} students`}>({tab.count})</span>
          </button>
        )
      })}
    </div>
  )
}
