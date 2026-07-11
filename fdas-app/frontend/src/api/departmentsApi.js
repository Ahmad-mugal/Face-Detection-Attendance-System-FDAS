import apiClient from './client'

export const departmentsApi = {
  list: () => apiClient.get('/api/departments').then(response => response.data),
  get: departmentId => apiClient.get(`/api/departments/${departmentId}`).then(response => response.data),
  create: payload => apiClient.post('/api/departments', payload).then(response => response.data),
  update: (departmentId, payload) => apiClient.patch(`/api/departments/${departmentId}`, payload).then(response => response.data),
  disable: departmentId => apiClient.patch(`/api/departments/${departmentId}/disable`).then(response => response.data),
  enable: departmentId => apiClient.patch(`/api/departments/${departmentId}/enable`).then(response => response.data),
}
