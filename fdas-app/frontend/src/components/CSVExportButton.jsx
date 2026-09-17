import Icon from './Icon'

/**
 * CSVExportButton — Triggers a CSV download from provided data
 * Phase 1: Client-side CSV generation from dummy data
 * Phase 6: Will call GET /api/reports/export from backend
 *
 * Props:
 *   data     - Array of objects to export
 *   filename - Name of the downloaded file
 *   label    - Button label text
 */
export default function CSVExportButton({ data = [], filename = 'fdas_report.csv', label = 'Export CSV' }) {
  const handleExport = () => {
    if (!data.length) return

    const headers = Object.keys(data[0])
    const csvRows = [
      headers.join(','),
      ...data.map(row =>
        headers.map(h => {
          const val = row[h] ?? ''
          const str = String(val).replace(/"/g, '""')
          return str.includes(',') || str.includes('"') || str.includes('\n') ? `"${str}"` : str
        }).join(',')
      ),
    ]
    const csvContent = csvRows.join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <button
      onClick={handleExport}
      disabled={!data.length}
      className="fdas-button fdas-button-warning"
      title={!data.length ? 'No data to export' : `Export ${data.length} records`}
    >
      <Icon name="download" size={18} />
      {label}
    </button>
  )
}
