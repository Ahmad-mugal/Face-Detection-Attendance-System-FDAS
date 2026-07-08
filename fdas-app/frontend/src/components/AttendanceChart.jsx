import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LineChart, Line, PieChart, Pie, Cell, ResponsiveContainer, Legend,
} from 'recharts'

const COLORS = { present: '#D4A017', absent: '#C4533A', total: '#934619' }

/**
 * AttendanceChart — Multi-type chart supporting bar, line, pie
 *
 * Props:
 *   type    - 'bar' | 'line' | 'pie'
 *   data    - Array of data objects
 *   title   - Chart title
 *   height  - Chart height in px (default 280)
 */
export default function AttendanceChart({ type = 'bar', data = [], title, height = 280 }) {
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    return (
      <div className="rounded-xl border p-3 text-sm shadow-lg" style={{ backgroundColor: '#FFF0E6', borderColor: '#dbc1b7' }}>
        <p className="font-bold mb-1" style={{ color: '#4A2B0F' }}>{label}</p>
        {payload.map(p => (
          <p key={p.dataKey} style={{ color: p.color }}>
            {p.dataKey === 'present' ? 'Present' : 'Absent'}: {p.value}%
          </p>
        ))}
      </div>
    )
  }

  const renderChart = () => {
    if (type === 'pie') {
      const total = data.reduce((s, d) => s + (d.value || 0), 0) || 1
      return (
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={3}
              dataKey="value"
            >
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.color || Object.values(COLORS)[i]} />
              ))}
            </Pie>
            <Tooltip formatter={(v) => [`${v} (${Math.round(v / total * 100)}%)`, '']} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )
    }

    if (type === 'line') {
      return (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0dfd8" />
            <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#887369' }} />
            <YAxis tick={{ fontSize: 11, fill: '#887369' }} domain={[60, 100]} />
            <Tooltip content={<CustomTooltip />} />
            <Line type="monotone" dataKey="present" stroke="#D4A017" strokeWidth={2.5} dot={{ fill: '#D4A017', r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      )
    }

    // Default: bar
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0dfd8" />
          <XAxis dataKey={data[0]?.day ? 'day' : 'month'} tick={{ fontSize: 11, fill: '#887369' }} />
          <YAxis tick={{ fontSize: 11, fill: '#887369' }} domain={[0, 100]} />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="present" fill="#D4A017" radius={[4, 4, 0, 0]} name="Present %" />
          <Bar dataKey="absent" fill="#C4533A" radius={[4, 4, 0, 0]} name="Absent %" />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  return (
    <div
      className="rounded-xl p-5"
      style={{ backgroundColor: '#FFF0E6', boxShadow: '0 4px 15px rgba(232,146,74,0.12)' }}
    >
      {title && (
        <h3 className="font-bold text-base mb-4" style={{ color: '#4A2B0F' }}>{title}</h3>
      )}
      <div style={{ width: '100%', minHeight: height }}>
        {renderChart()}
      </div>
    </div>
  )
}
