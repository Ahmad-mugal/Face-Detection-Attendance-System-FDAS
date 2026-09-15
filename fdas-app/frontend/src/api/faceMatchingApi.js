import apiClient from './client'

export const faceMatchingApi = {
  getDeepInfo: () => apiClient.get('/api/deep-face/info').then(response => response.data),
  validateSingleFace: ({ file, referenceFile, attendanceMode = false }) => {
    const formData = new FormData()
    formData.append('file', file, `single_face_check_${Date.now()}.jpg`)
    if (referenceFile) formData.append('referenceFile', referenceFile, 'locked_face_reference.jpg')
    formData.append('attendanceMode', attendanceMode ? 'true' : 'false')
    return apiClient.post('/api/face-processing/validate-single-face', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
  diagnose: ({ departmentId, expectedStudentId, file }) => {
    const formData = new FormData()
    formData.append('departmentId', departmentId)
    if (expectedStudentId) formData.append('expectedStudentId', expectedStudentId)
    formData.append('file', file, `identity_diagnostic_${Date.now()}.jpg`)
    return apiClient.post('/api/face-matching/diagnose', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
  diagnoseDeep: ({ departmentId, expectedStudentId, file }) => {
    const formData = new FormData()
    formData.append('file', file, `deep_identity_query_${Date.now()}.jpg`)
    return apiClient.post('/api/deep-face/match/diagnostic', formData, {
      params: { departmentId, expectedStudentId },
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
}
