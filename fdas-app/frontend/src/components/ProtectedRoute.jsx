import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

export default function ProtectedRoute({ role }) {
  const { accessToken, currentUser, initializing, isAdmin, isOperator } = useAuth()
  const location = useLocation()

  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#FAF4EC', color: '#934619' }}>
        Loading FDAS session...
      </div>
    )
  }

  if (!accessToken || !currentUser) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (role === 'admin' && !isAdmin()) {
    return <Navigate to="/user/dashboard" replace />
  }

  if (role === 'user') {
    if (isAdmin()) {
      return <Navigate to="/admin/dashboard" replace />
    }
    if (!isOperator()) {
      return <Navigate to="/login" replace />
    }
  }

  return <Outlet />
}
