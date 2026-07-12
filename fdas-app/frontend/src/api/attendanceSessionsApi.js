import apiClient from './client'

export const attendanceSessionsApi = {
  start: payload => apiClient.post('/api/attendance-sessions/start', payload).then(response => response.data),
  stop: sessionId => apiClient.post(`/api/attendance-sessions/${sessionId}/stop`).then(response => response.data),
  active: params => apiClient.get('/api/attendance-sessions/active', { params }).then(response => response.data),
  records: sessionId => apiClient.get(`/api/attendance-sessions/${sessionId}/records`).then(response => response.data),
}
