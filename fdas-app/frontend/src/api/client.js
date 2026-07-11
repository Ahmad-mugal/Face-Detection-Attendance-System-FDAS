import axios from 'axios'

export const API_BASE_URL = 'http://127.0.0.1:8000'
export const TOKEN_STORAGE_KEY = 'fdas_access_token'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function setStoredToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  }
}

export function getApiError(error, fallback = 'Something went wrong. Please try again.') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map(item => item.msg || item.detail).filter(Boolean).join(' ')
  }
  if (typeof detail === 'string') return detail
  if (error?.message) return error.message
  return fallback
}

apiClient.interceptors.request.use(config => {
  const token = getStoredToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default apiClient
