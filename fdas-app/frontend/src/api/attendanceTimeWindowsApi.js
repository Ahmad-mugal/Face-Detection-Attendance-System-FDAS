import apiClient from './client'

export const attendanceTimeWindowsApi = {
  list: () => apiClient.get('/api/attendance-time-windows').then(response => response.data),
  get: windowId => apiClient.get(`/api/attendance-time-windows/${windowId}`).then(response => response.data),
  create: payload => apiClient.post('/api/attendance-time-windows', payload).then(response => response.data),
  update: (windowId, payload) => apiClient.patch(`/api/attendance-time-windows/${windowId}`, payload).then(response => response.data),
  activate: windowId => apiClient.patch(`/api/attendance-time-windows/${windowId}/activate`).then(response => response.data),
  deactivate: windowId => apiClient.patch(`/api/attendance-time-windows/${windowId}/deactivate`).then(response => response.data),
}
