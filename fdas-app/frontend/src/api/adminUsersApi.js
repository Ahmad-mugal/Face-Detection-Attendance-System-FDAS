import apiClient from './client'

export const adminUsersApi = {
  listUsers: () => apiClient.get('/api/admin/users').then(response => response.data),
  listRequests: () => apiClient.get('/api/admin/user-requests').then(response => response.data),
  emailStatus: () => apiClient.get('/api/admin/email-status').then(response => response.data),
  approve: (userId, payload) => apiClient.patch(`/api/admin/users/${userId}/approve`, payload).then(response => response.data),
  resendApprovalEmail: userId => apiClient.post(`/api/admin/users/${userId}/resend-approval-email`).then(response => response.data),
  reject: userId => apiClient.patch(`/api/admin/users/${userId}/reject`).then(response => response.data),
  disable: userId => apiClient.patch(`/api/admin/users/${userId}/disable`).then(response => response.data),
  enable: userId => apiClient.patch(`/api/admin/users/${userId}/enable`).then(response => response.data),
  updateAccess: (userId, payload) => apiClient.patch(`/api/admin/users/${userId}/access`, payload).then(response => response.data),
  delete: userId => apiClient.delete(`/api/admin/users/${userId}`).then(response => response.data),
  generatePasswordRecoveryCode: userId => apiClient.post(`/api/admin/users/${userId}/password-recovery-code`).then(response => response.data),
}
