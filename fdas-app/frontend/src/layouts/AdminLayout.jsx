import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { useAttendanceSession } from '../context/useAttendanceSession'
import { useAuth } from '../context/useAuth'
import Icon from '../components/Icon'
import { useSmartHeader } from '../hooks/useSmartHeader'
import NotificationBell from '../components/NotificationBell'

const navLinks = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: 'dashboard' },
  { to: '/admin/students', label: 'Students', icon: 'group' },
  { to: '/admin/attendance/live', label: 'Attendance', icon: 'event_available' },
  { to: '/admin/analytics', label: 'Analytics', icon: 'bar_chart' },
];

const settingsLinks = [
  { to: '/admin/requests', label: 'Pending Requests', icon: 'pending_actions' },
  { to: '/admin/users', label: 'Manage Users', icon: 'manage_accounts' },
  { to: '/admin/classes', label: 'Manage Classes', icon: 'school' },
  { to: '/admin/timing', label: 'Attendance Timing', icon: 'schedule' },
];

export default function AdminLayout() {
  const navRef = useRef(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { confirmNavigation } = useAttendanceSession()
  const { currentUser, logout } = useAuth()
  const headerVisible = useSmartHeader({
    routeKey: location.pathname,
    locked: settingsOpen || notificationsOpen || profileOpen || mobileMenuOpen,
  })

  const isSettingsActive = settingsLinks.some(l => location.pathname.startsWith(l.to))
  const closeDropdowns = () => {
    setSettingsOpen(false)
    setNotificationsOpen(false)
    setProfileOpen(false)
  }

  const handleGuardedNavClick = (to, event) => {
    if (!confirmNavigation(to, location.pathname)) {
      event.preventDefault()
      return
    }
    closeDropdowns()
    setMobileMenuOpen(false)
  }

  const guardedNavigate = to => {
    const completeNavigation = () => {
      if (to === '/login') logout()
      closeDropdowns()
      setMobileMenuOpen(false)
      navigate(to)
    }
    if (!confirmNavigation(to, location.pathname, completeNavigation)) return
    completeNavigation()
  }

  useEffect(() => {
    closeDropdowns()
    setMobileMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    const handlePointerDown = event => {
      if (!navRef.current?.contains(event.target)) closeDropdowns()
    }
    const handleKeyDown = event => {
      if (event.key === 'Escape') {
        closeDropdowns()
        setMobileMenuOpen(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FAF4EC' }}>
      {/* Top Navigation Bar */}
      <nav
        ref={navRef}
        className={`fdas-smart-header sticky top-0 z-50 w-full border-b-2 ${headerVisible ? '' : 'fdas-smart-header-hidden'}`}
        data-smart-header
        data-visible={headerVisible}
        style={{
          backgroundColor: '#fff8f6',
          borderColor: '#C4533A',
          boxShadow: '0 4px 12px rgba(232,146,74,0.15)',
        }}
      >
        <div className="fdas-shell flex items-center justify-between h-16 min-w-0 gap-2">
          {/* Logo */}
          <NavLink to="/admin/dashboard" onClick={event => handleGuardedNavClick('/admin/dashboard', event)} className="flex items-center gap-1.5 select-none shrink-0">
            <Icon name="school" size={22} style={{ color: '#D4A017' }} />
            <span className="text-xl font-black tracking-tight" style={{ color: '#C4533A' }}>FDAS</span>
          </NavLink>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center justify-center gap-0.5 h-full flex-1 min-w-0">
            {navLinks.map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={event => handleGuardedNavClick(link.to, event)}
                className={({ isActive }) =>
                  `flex items-center gap-1 px-2 lg:px-3 py-2 rounded-lg font-semibold text-xs lg:text-sm whitespace-nowrap transition-all duration-200 ${
                    isActive
                      ? 'text-[#C4533A] border-b-2 border-[#D4A017] rounded-none pb-[14px]'
                      : 'text-[#4A2B0F] opacity-80 hover:text-[#C4533A] hover:bg-orange-50'
                  }`
                }
              >
                <Icon name={link.icon} size={18} />
                {link.label}
              </NavLink>
            ))}

            {/* Settings Dropdown */}
            <div className="relative">
              <button
                onClick={() => {
                  setSettingsOpen(current => !current)
                  setNotificationsOpen(false)
                  setProfileOpen(false)
                }}
                className={`flex items-center gap-1 px-2 lg:px-3 py-2 rounded-lg font-semibold text-xs lg:text-sm whitespace-nowrap transition-all duration-200 ${
                  isSettingsActive
                    ? 'text-[#C4533A] border-b-2 border-[#D4A017] rounded-none pb-[14px]'
                    : 'text-[#4A2B0F] opacity-80 hover:text-[#C4533A] hover:bg-orange-50'
                }`}
              >
                <Icon name="settings" size={18} />
                Settings
                <Icon name={settingsOpen ? 'expand_less' : 'expand_more'} size={16} />
              </button>

              {settingsOpen && (
                <div
                  className="absolute top-full right-0 mt-1 w-56 rounded-xl border shadow-lg z-50"
                  style={{ backgroundColor: '#fff8f6', borderColor: '#dbc1b7', boxShadow: '0 8px 24px rgba(232,146,74,0.2)' }}
                >
                  {settingsLinks.map(link => (
                    <NavLink
                      key={link.to}
                      to={link.to}
                      onClick={event => handleGuardedNavClick(link.to, event)}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all ${
                          isActive
                            ? 'text-[#C4533A] bg-orange-50 font-bold'
                            : 'text-[#4A2B0F] hover:bg-orange-50 hover:text-[#C4533A]'
                        } first:rounded-t-xl last:rounded-b-xl`
                      }
                    >
                      <Icon name={link.icon} size={18} />
                      {link.label}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Side */}
          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            <NotificationBell
              open={notificationsOpen}
              onToggle={() => {
                setNotificationsOpen(current => !current)
                setSettingsOpen(false)
                setProfileOpen(false)
              }}
              onNavigate={guardedNavigate}
            />
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setProfileOpen(current => !current)
                  setSettingsOpen(false)
                  setNotificationsOpen(false)
                }}
                onPointerDown={event => event.stopPropagation()}
                className="flex items-center gap-2 rounded-full p-1 transition-colors hover:bg-orange-50"
                aria-label="Open profile menu"
                aria-haspopup="menu"
                aria-expanded={profileOpen}
              >
                <div className="w-9 h-9 rounded-full border-2 flex items-center justify-center font-bold text-white text-sm" style={{ backgroundColor: '#C4533A', borderColor: '#D4A017' }}>
                  {(currentUser?.fullName || 'Admin').charAt(0)}
                </div>
                <div className="hidden lg:block text-left min-w-0 max-w-48 xl:max-w-64">
                  <div className="text-xs font-bold truncate" style={{ color: '#4A2B0F' }}>{currentUser?.fullName || 'Admin'}</div>
                  <div className="text-[10px]" style={{ color: '#887369' }}>{currentUser?.role || 'Administrator'}</div>
                </div>
              </button>
              {profileOpen && (
                <div role="menu" className="absolute right-0 top-full mt-2 w-56 max-w-[calc(100vw-1rem)] rounded-xl border p-2 z-50" style={{ backgroundColor: '#fff8f6', borderColor: '#dbc1b7', boxShadow: '0 8px 24px rgba(232,146,74,0.2)' }}>
                  <div className="px-3 py-2 border-b mb-1" style={{ borderColor: '#f0dfd8' }}>
                    <p className="text-sm font-bold" style={{ color: '#4A2B0F' }}>{currentUser?.fullName || 'Admin User'}</p>
                    <p className="text-xs" style={{ color: '#887369' }}>{currentUser?.email || 'admin@fdas.local'}</p>
                  </div>
                  <button role="menuitem" onClick={() => guardedNavigate('/account/profile')} className="fdas-menu-item">View Profile</button>
                  <button role="menuitem" onClick={() => guardedNavigate('/account/preferences')} className="fdas-menu-item">Account Preferences</button>
                  <button role="menuitem" onClick={() => guardedNavigate('/login')} className="fdas-menu-item fdas-menu-item-danger">Logout</button>
                </div>
              )}
            </div>

            {/* Mobile Menu */}
            <button className="fdas-icon-button fdas-mobile-nav-button" style={{ color: '#C4533A' }} onClick={() => setMobileMenuOpen(!mobileMenuOpen)} aria-label={mobileMenuOpen ? 'Close navigation' : 'Open navigation'} title={mobileMenuOpen ? 'Close navigation' : 'Open navigation'}>
              <Icon name={mobileMenuOpen ? 'close' : 'menu'} size={20} />
            </button>
          </div>
        </div>

        {/* Mobile Menu Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t px-4 py-3 space-y-1" style={{ borderColor: '#dbc1b7', backgroundColor: '#fff8f6' }}>
            {[...navLinks, ...settingsLinks].map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={event => handleGuardedNavClick(link.to, event)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive ? 'bg-orange-100 text-[#C4533A] font-bold' : 'text-[#4A2B0F] hover:bg-orange-50'
                  }`
                }
              >
                <Icon name={link.icon} size={18} />
                {link.label}
              </NavLink>
            ))}
            <button
              onClick={() => guardedNavigate('/login')}
              className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium w-full text-left"
              style={{ color: '#ba1a1a' }}
            >
              <Icon name="logout" size={18} />
              Logout
            </button>
          </div>
        )}
      </nav>

      {/* Page Content */}
      <main className="fdas-shell fdas-shell-content min-w-0">
        <Outlet />
      </main>
    </div>
  )
}
