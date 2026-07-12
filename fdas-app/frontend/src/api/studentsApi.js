import apiClient from './client'

export const studentsApi = {
  list: params => apiClient.get('/api/students', { params }).then(response => response.data),
  get: studentId => apiClient.get(`/api/students/${studentId}`).then(response => response.data),
  create: payload => apiClient.post('/api/students', payload).then(response => response.data),
  update: (studentId, payload) => apiClient.patch(`/api/students/${studentId}`, payload).then(response => response.data),
  disable: studentId => apiClient.patch(`/api/students/${studentId}/disable`).then(response => response.data),
  enable: studentId => apiClient.patch(`/api/students/${studentId}/enable`).then(response => response.data),
  uploadFaceEnrollment: (studentId, files) => {
    const formData = new FormData()
    files.forEach((file, index) => {
      formData.append('files', file, `face_sample_${String(index + 1).padStart(2, '0')}.jpg`)
    })
    return apiClient.post(`/api/students/${studentId}/face-enrollment/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
}
