import apiClient from './client'

export const attendanceMarkingApi = {
  markByFace: ({ sessionId, file }) => {
    const formData = new FormData()
    formData.append('sessionId', sessionId)
    formData.append('file', file, `attendance_scan_${Date.now()}.jpg`)
    return apiClient.post('/api/attendance/mark-by-face', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
  markByFaceLive: ({ sessionId, challengeType, files }) => {
    const formData = new FormData()
    formData.append('sessionId', sessionId)
    formData.append('challengeType', challengeType)
    files.forEach((file, index) => {
      formData.append('files', file, `liveness_frame_${index + 1}_${Date.now()}.jpg`)
    })
    return apiClient.post('/api/attendance/mark-by-face-live', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(response => response.data)
  },
}
