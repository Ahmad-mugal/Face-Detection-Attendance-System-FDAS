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
}
