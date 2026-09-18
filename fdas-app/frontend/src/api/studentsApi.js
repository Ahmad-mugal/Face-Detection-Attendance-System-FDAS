import apiClient from './client'

function downloadResponse(response, fallbackFilename) {
  const disposition = response.headers['content-disposition'] || ''
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || fallbackFilename
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function importForm(file) {
  const formData = new FormData()
  formData.append('file', file, file.name)
  return formData
}

export const studentsApi = {
  list: params => apiClient.get('/api/students', { params }).then(response => response.data),
  get: studentId => apiClient.get(`/api/students/${studentId}`).then(response => response.data),
  create: payload => apiClient.post('/api/students', payload).then(response => response.data),
  update: (studentId, payload) => apiClient.patch(`/api/students/${studentId}`, payload).then(response => response.data),
  disable: studentId => apiClient.patch(`/api/students/${studentId}/disable`).then(response => response.data),
  enable: studentId => apiClient.patch(`/api/students/${studentId}/enable`).then(response => response.data),
  delete: studentId => apiClient.delete(`/api/students/${studentId}`).then(response => response.data),
  downloadImportTemplate: () => apiClient.get('/api/students/import/template', { responseType: 'blob' }).then(response => downloadResponse(response, 'FDAS_Student_Import_Template.csv')),
  validateImport: file => apiClient.post('/api/students/import/validate', importForm(file), { headers: { 'Content-Type': 'multipart/form-data' } }).then(response => response.data),
  confirmImport: file => apiClient.post('/api/students/import/confirm', importForm(file), { headers: { 'Content-Type': 'multipart/form-data' } }).then(response => response.data),
  downloadImportErrors: file => apiClient.post('/api/students/import/error-report', importForm(file), { headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob' }).then(response => downloadResponse(response, 'FDAS_Student_Import_Errors.csv')),
  uploadFaceEnrollment: (studentId, files) => {
    const formData = new FormData()
    files.forEach((file, index) => {
      formData.append('files', file, `face_sample_${String(index + 1).padStart(2, '0')}.jpg`)
    })
    return apiClient.post(`/api/students/${studentId}/face-enrollment/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
  getDeepEnrollmentReadiness: studentId => apiClient
    .get(`/api/students/${studentId}/deep-enrollment/readiness`)
    .then(response => response.data),
  validateDeepRecoverySample: file => {
    const formData = new FormData()
    formData.append('file', file, `deep_recovery_check_${Date.now()}.jpg`)
    return apiClient.post('/api/deep-face/validate-recovery-sample', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
  uploadDeepRecovery: (studentId, files) => {
    const formData = new FormData()
    files.forEach((file, index) => {
      formData.append('files', file, `deep_recovery_${String(index + 1).padStart(2, '0')}.jpg`)
    })
    return apiClient.post(`/api/students/${studentId}/deep-enrollment/recovery`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
}
