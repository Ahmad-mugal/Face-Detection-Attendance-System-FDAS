import { Routes, Route, Navigate } from 'react-router-dom'

import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import AdminCodeResetPage from './pages/AdminCodeResetPage'
import ProtectedRoute from './components/ProtectedRoute'

import AdminLayout from './layouts/AdminLayout'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminStudents from './pages/admin/AdminStudents'
import AdminAddStudent from './pages/admin/AdminAddStudent'
import AdminLiveAttendance from './pages/admin/AdminLiveAttendance'
import AdminAnalytics from './pages/admin/AdminAnalytics'
import AdminRequests from './pages/admin/AdminRequests'
import AdminUsers from './pages/admin/AdminUsers'
import AdminClasses from './pages/admin/AdminClasses'
import AdminTiming from './pages/admin/AdminTiming'

import UserLayout from './layouts/UserLayout'
import UserDashboard from './pages/user/UserDashboard'
import UserStudents from './pages/user/UserStudents'
import UserAddStudent from './pages/user/UserAddStudent'
import UserAttendance from './pages/user/UserAttendance'
import UserReports from './pages/user/UserReports'
import AccountLayout from './layouts/AccountLayout'
import AccountProfile from './pages/account/AccountProfile'
import AccountPreferences from './pages/account/AccountPreferences'

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/reset-password/admin-code" element={<AdminCodeResetPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/account" element={<AccountLayout />}>
          <Route path="profile" element={<AccountProfile />} />
          <Route path="preferences" element={<AccountPreferences />} />
        </Route>
      </Route>

      {/* Admin Routes */}
      <Route element={<ProtectedRoute role="admin" />}>
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="dashboard" element={<AdminDashboard />} />
          <Route path="students" element={<AdminStudents />} />
          <Route path="students/add" element={<AdminAddStudent />} />
          <Route path="attendance/live" element={<AdminLiveAttendance />} />
          <Route path="analytics" element={<AdminAnalytics />} />
          <Route path="requests" element={<AdminRequests />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="classes" element={<AdminClasses />} />
          <Route path="timing" element={<AdminTiming />} />
        </Route>
      </Route>

      {/* User/Operator Routes */}
      <Route element={<ProtectedRoute role="user" />}>
        <Route path="/user" element={<UserLayout />}>
          <Route index element={<Navigate to="/user/dashboard" replace />} />
          <Route path="dashboard" element={<UserDashboard />} />
          <Route path="students" element={<UserStudents />} />
          <Route path="students/add" element={<UserAddStudent />} />
          <Route path="attendance" element={<UserAttendance />} />
          <Route path="reports" element={<UserReports />} />
        </Route>
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
