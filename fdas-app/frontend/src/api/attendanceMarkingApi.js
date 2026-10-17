import apiClient from './client'

export const attendanceMarkingApi = {
  markByFaceFast: ({ sessionId, file }) => {
    const formData = new FormData()
    formData.append('sessionId', sessionId)
    formData.append('file', file, `fast_attendance_frame_${Date.now()}.jpg`)
    return apiClient.post('/api/attendance/mark-by-face-fast', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
  markByFace: ({ sessionId, file }) => {
    const formData = new FormData()
    formData.append('sessionId', sessionId)
    formData.append('file', file, `attendance_scan_${Date.now()}.jpg`)
    return apiClient.post('/api/attendance/mark-by-face', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
  markByFaceLive: ({ sessionId, challengeType, files, queryFiles = [], controlledTest = false, expectedStudentId }) => {
    const formData = new FormData()
    formData.append('sessionId', sessionId)
    formData.append('challengeType', challengeType)
    formData.append('controlledTest', controlledTest ? 'true' : 'false')
    if (expectedStudentId) formData.append('expectedStudentId', expectedStudentId)
    files.forEach((file, index) => {
      formData.append('files', file, `liveness_frame_${index + 1}_${Date.now()}.jpg`)
    })
    queryFiles.forEach((file, index) => {
      formData.append('queryFiles', file, `recognition_query_${index + 1}_${Date.now()}.jpg`)
    })
    return apiClient.post('/api/attendance/mark-by-face-live', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
}
