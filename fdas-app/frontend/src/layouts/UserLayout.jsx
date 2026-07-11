import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { useAttendanceSession } from '../context/useAttendanceSession'
import { useAuth } from '../context/useAuth'
import Icon from '../components/Icon'

const sideNavLinks = [
  { to: '/user/dashboard', label: 'Dashboard', icon: 'dashboard' },
  { to: '/user/students', label: 'Students', icon: 'group' },
  { to: '/user/students/add', label: 'Add Student', icon: 'person_add' },
  { to: '/user/attendance', label: 'Attendance', icon: 'event_available' },
  { to: '/user/reports', label: 'Reports', icon: 'assessment' },
];

export default function UserLayout() {
  const headerRef = useRef(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { confirmNavigation } = useAttendanceSession()
  const { currentUser, logout } = useAuth()
  const operatorName = currentUser?.fullName || 'Operator'
  const operatorDepartment = currentUser?.assignedDepartmentName || (currentUser?.accessScope === 'AllDepartments' ? 'All Departments' : 'Assigned Department')
  const operatorInitials = operatorName.split(' ').map(part => part.charAt(0)).join('').slice(0, 2).toUpperCase() || 'OP'

  const closeDropdowns = () => {
    setNotificationsOpen(false)
    setProfileOpen(false)
  }

  const handleGuardedNavClick = (to, event) => {
    if (!confirmNavigation(to, location.pathname)) {
      event.preventDefault()
      return
    }
    closeDropdowns()
    setMobileOpen(false)
  }

  const guardedNavigate = to => {
    if (!confirmNavigation(to, location.pathname)) return
    if (to === '/login') logout()
    closeDropdowns()
    setMobileOpen(false)
    navigate(to)
  }

  useEffect(() => {
    closeDropdowns()
    setMobileOpen(false)
  }, [location.pathname])

  useEffect(() => {
    const handlePointerDown = event => {
      if (!headerRef.current?.contains(event.target)) closeDropdowns()
    }
    const handleKeyDown = event => {
      if (event.key === 'Escape') {
        closeDropdowns()
        setMobileOpen(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  const Sidebar = () => (
    <div className="flex flex-col h-full">
      {/* Brand */}
      <div className="px-6 mb-8 pt-2">
        <h2 className="text-2xl font-black" style={{ color: '#C4533A' }}>FDAS Operator</h2>
        <div className="flex items-center gap-1.5 mt-1">
          <Icon name="domain" size={14} style={{ color: '#D4A017' }} />
          <p className="text-xs font-semibold" style={{ color: '#887369' }}>Dept: {operatorDepartment}</p>
        </div>
      </div>

      {/* Nav Links */}
      <nav className="flex-1 px-2 space-y-1">
        {sideNavLinks.map(link => {
          const isCurrentRoute = location.pathname === link.to

          return (
            <NavLink
              key={link.to}
              to={link.to}
              onClick={event => handleGuardedNavClick(link.to, event)}
              className={`flex items-center gap-3 mx-1 px-4 py-3 rounded-xl font-medium text-sm transition-all duration-150 ${
                isCurrentRoute
                  ? 'font-bold scale-[0.97]'
                  : 'hover:bg-[#f0dfd8]'
              }`}
              style={isCurrentRoute
                ? { backgroundColor: '#ffc641', color: '#715300' }
                : { color: '#55433b' }
              }
              aria-current={isCurrentRoute ? 'page' : undefined}
            >
              <>
                <Icon name={link.icon} size={20} />
                {link.label}
              </>
            </NavLink>
          )
        })}
      </nav>

      {/* Bottom: Profile + Logout */}
      <div className="px-2 pb-4 mt-auto space-y-1">
        <div className="mx-1 px-4 py-3 rounded-xl flex items-center gap-3" style={{ backgroundColor: '#fceae4' }}>
          <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white" style={{ backgroundColor: '#C4533A' }}>
            {operatorInitials}
          </div>
          <div>
            <div className="text-xs font-bold truncate" style={{ color: '#4A2B0F', maxWidth: 120 }}>{operatorName}</div>
            <div
              className="text-[10px] px-1.5 py-0.5 rounded-full font-semibold inline-block mt-0.5"
              style={{ backgroundColor: '#D4A017', color: '#fff' }}
            >
              Dept Access
            </div>
          </div>
        </div>
        <button
          onClick={() => guardedNavigate('/login')}
          className="flex items-center gap-3 mx-1 px-4 py-3 rounded-xl font-medium text-sm w-full text-left transition-all hover:bg-red-50"
          style={{ color: '#ba1a1a' }}
        >
          <Icon name="logout" size={20} />
          Logout
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex h-screen overflow-hidden max-w-full" style={{ backgroundColor: '#FAF4EC' }}>
      {/* Desktop Sidebar */}
      <aside
        className="hidden md:flex flex-col w-64 h-screen fixed left-0 top-0 border-r z-50"
        style={{
          backgroundColor: '#fff1eb',
          borderColor: '#dbc1b7',
          boxShadow: '4px 0 12px rgba(232,146,74,0.15)',
        }}
      >
        <Sidebar />
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="w-64 h-full flex flex-col border-r" style={{ backgroundColor: '#fff1eb', borderColor: '#dbc1b7' }}>
            <Sidebar />
          </div>
          <div className="flex-1 bg-black/40" onClick={() => setMobileOpen(false)} />
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-col flex-1 md:ml-64 overflow-hidden min-w-0">
        {/* Top bar */}
        <header
          ref={headerRef}
          className="sticky top-0 z-40 flex items-center justify-between px-4 sm:px-6 h-16 border-b min-w-0"
          style={{ backgroundColor: '#fff8f6', borderColor: '#dbc1b7', boxShadow: '0 2px 8px rgba(232,146,74,0.1)' }}
        >
          <div className="flex items-center gap-3">
            <button className="md:hidden p-1.5 rounded-lg" style={{ color: '#C4533A' }} onClick={() => setMobileOpen(true)}>
              <Icon name="menu" size={20} />
            </button>
            <span className="font-bold text-lg truncate" style={{ color: '#C4533A' }}>FDAS Portal</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="relative">
              <button
                onClick={() => {
                  setNotificationsOpen(current => !current)
                  setProfileOpen(false)
                }}
                className="p-2 rounded-full hover:bg-orange-50 transition-colors relative"
                style={{ color: '#887369' }}
                aria-label="Open notifications"
              >
                <Icon name="notifications" size={20} />
                <span className="absolute top-2 right-2 w-2 h-2 rounded-full" style={{ backgroundColor: '#D4A017' }} />
              </button>
              {notificationsOpen && (
                <div className="absolute right-0 top-full mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-xl border p-3 z-50" style={{ backgroundColor: '#fff8f6', borderColor: '#dbc1b7', boxShadow: '0 8px 24px rgba(232,146,74,0.2)' }}>
                  <p className="text-xs font-black uppercase tracking-wide mb-2" style={{ color: '#C4533A' }}>Notifications</p>
                  {['Attendance window closes at 09:30', '2 students still need face enrollment', 'Duplicate face attempt blocked in demo log'].map(item => (
                    <div key={item} className="rounded-lg px-3 py-2 text-sm mb-2 last:mb-0" style={{ backgroundColor: '#FFF0E6', color: '#55433b' }}>{item}</div>
                  ))}
                </div>
              )}
            </div>
            <button
              onClick={closeDropdowns}
              className="p-2 rounded-full hover:bg-orange-50 transition-colors"
              style={{ color: '#887369' }}
              aria-label="Settings"
            >
              <Icon name="settings" size={20} />
            </button>
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setProfileOpen(current => !current)
                  setNotificationsOpen(false)
                }}
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white border-2"
                style={{ backgroundColor: '#C4533A', borderColor: '#D4A017' }}
                aria-label="Open profile menu"
              >
                {operatorInitials}
              </button>
              {profileOpen && (
                <div className="absolute right-0 top-full mt-2 w-56 rounded-xl border p-2 z-50" style={{ backgroundColor: '#fff8f6', borderColor: '#dbc1b7', boxShadow: '0 8px 24px rgba(232,146,74,0.2)' }}>
                  <div className="px-3 py-2 border-b mb-1" style={{ borderColor: '#f0dfd8' }}>
                    <p className="text-sm font-bold" style={{ color: '#4A2B0F' }}>{operatorName}</p>
                    <p className="text-xs" style={{ color: '#887369' }}>{operatorDepartment}</p>
                  </div>
                  <button className="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-orange-50" style={{ color: '#55433b' }}>Profile</button>
                  <button onClick={() => guardedNavigate('/login')} className="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-red-50" style={{ color: '#ba1a1a' }}>Logout</button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1280px] mx-auto px-4 sm:px-6 py-6 w-full min-w-0">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
