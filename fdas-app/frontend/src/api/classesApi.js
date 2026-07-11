import apiClient from './client'

export const classesApi = {
  list: params => apiClient.get('/api/classes', { params }).then(response => response.data),
  get: classId => apiClient.get(`/api/classes/${classId}`).then(response => response.data),
  create: payload => apiClient.post('/api/classes', payload).then(response => response.data),
  update: (classId, payload) => apiClient.patch(`/api/classes/${classId}`, payload).then(response => response.data),
  archive: classId => apiClient.patch(`/api/classes/${classId}/archive`).then(response => response.data),
  activate: classId => apiClient.patch(`/api/classes/${classId}/activate`).then(response => response.data),
}
