import axios from 'axios'

export const API_BASE_URL = 'http://127.0.0.1:8000'
export const TOKEN_STORAGE_KEY = 'fdas_access_token'
export const FDAS_SERVER_UNAVAILABLE_MESSAGE = 'Unable to connect to the FDAS server. Please make sure the backend is running.'

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

export function isNetworkError(error) {
  return !error?.response && Boolean(
    error?.request
    || error?.code === 'ERR_NETWORK'
    || error?.message === 'Network Error',
  )
}

export function getApiError(error, fallback = 'Something went wrong. Please try again.') {
  if (isNetworkError(error)) return FDAS_SERVER_UNAVAILABLE_MESSAGE

  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail
      .map(item => item.msg || item.detail)
      .filter(Boolean)
      .map(message => message.replace(/^Value error,\s*/i, ''))
      .join(' ')
  }
  if (typeof detail === 'string') return detail
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
