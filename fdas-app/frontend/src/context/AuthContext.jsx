import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi } from '../api/authApi'
import { getApiError, getStoredToken, setStoredToken } from '../api/client'
import { AuthContext } from './authCore'

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken] = useState(getStoredToken())
  const [currentUser, setCurrentUser] = useState(null)
  const [initializing, setInitializing] = useState(Boolean(getStoredToken()))

  const applySession = useCallback((token, user) => {
    setStoredToken(token)
    setAccessToken(token)
    setCurrentUser(user)
  }, [])

  const logout = useCallback(() => {
    applySession(null, null)
  }, [applySession])

  const loadCurrentUser = useCallback(async () => {
    if (!getStoredToken()) {
      setCurrentUser(null)
      setInitializing(false)
      return null
    }
    try {
      const user = await authApi.me()
      setCurrentUser(user)
      return user
    } catch {
      logout()
      return null
    } finally {
      setInitializing(false)
    }
  }, [logout])

  const login = useCallback(async (email, password) => {
    try {
      const result = await authApi.login({ email, password })
      applySession(result.accessToken, result.user)
      return result.user
    } catch (error) {
      throw new Error(getApiError(error, 'Login failed.'))
    }
  }, [applySession])

  useEffect(() => {
    loadCurrentUser()
  }, [loadCurrentUser])

  const value = useMemo(() => ({
    accessToken,
    currentUser,
    role: currentUser?.role || null,
    status: currentUser?.status || null,
    accessScope: currentUser?.accessScope || null,
    assignedDepartmentId: currentUser?.assignedDepartmentId || null,
    assignedDepartmentName: currentUser?.assignedDepartmentName || null,
    initializing,
    login,
    logout,
    loadCurrentUser,
    isAdmin: () => currentUser?.role === 'Admin',
    isOperator: () => currentUser?.role === 'User',
    hasAllDepartmentsAccess: () => currentUser?.accessScope === 'AllDepartments',
  }), [accessToken, currentUser, initializing, loadCurrentUser, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
