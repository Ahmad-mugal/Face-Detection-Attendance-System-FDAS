import apiClient from './client'

function compactParams(params = {}) {
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined))
}

export const attendanceRecordsApi = {
  list: params => apiClient.get('/api/attendance-records', { params: compactParams(params) }).then(response => response.data),
  summary: params => apiClient.get('/api/attendance-records/summary', { params: compactParams(params) }).then(response => response.data),
  exportCsv: params => apiClient.get('/api/attendance-records/export.csv', {
    params: compactParams(params),
    responseType: 'blob',
  }).then(response => response.data),
}
