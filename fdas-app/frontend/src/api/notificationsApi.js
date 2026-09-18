import apiClient from './client'

export const notificationsApi = {
  list: (limit = 30) => apiClient.get('/api/notifications', { params: { limit } }).then(response => response.data),
  unreadCount: () => apiClient.get('/api/notifications/unread-count').then(response => response.data),
  markRead: notificationId => apiClient.patch(`/api/notifications/${notificationId}/read`).then(response => response.data),
  markAllRead: () => apiClient.post('/api/notifications/mark-all-read').then(response => response.data),
}
