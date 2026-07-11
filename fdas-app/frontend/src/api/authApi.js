import apiClient from './client'

export const authApi = {
  login: payload => apiClient.post('/api/auth/login', payload).then(response => response.data),
  me: () => apiClient.get('/api/auth/me').then(response => response.data),
  registerRequest: payload => apiClient.post('/api/auth/register-request', payload).then(response => response.data),
}
