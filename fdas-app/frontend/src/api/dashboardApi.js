import apiClient from './client'

export const dashboardApi = {
  getSummary: () => apiClient.get('/api/dashboard/summary').then(response => response.data),
}
