import { Routes, Route, Navigate } from 'react-router-dom'

import LoginPage from './pages/LoginPage'

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

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />

      {/* Admin Routes */}
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

      {/* User/Operator Routes */}
      <Route path="/user" element={<UserLayout />}>
        <Route index element={<Navigate to="/user/dashboard" replace />} />
        <Route path="dashboard" element={<UserDashboard />} />
        <Route path="students" element={<UserStudents />} />
        <Route path="students/add" element={<UserAddStudent />} />
        <Route path="attendance" element={<UserAttendance />} />
        <Route path="reports" element={<UserReports />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
