import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import Icon from '../components/Icon'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const email = form.email.trim().toLowerCase()
      if (!email || !form.password.trim()) {
        setError('Please enter your email and password.')
        return
      }
      const user = await login(email, form.password)
      const fallbackPath = user.role === 'Admin' ? '/admin/dashboard' : '/user/dashboard'
      navigate(location.state?.from || fallbackPath, { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 sm:p-6"
      style={{ backgroundColor: '#FAF4EC' }}
    >
      <main
        className="w-full max-w-5xl min-h-[520px] flex flex-col lg:flex-row rounded-2xl overflow-hidden"
        style={{ boxShadow: '0 8px 40px rgba(232,146,74,0.2)' }}
      >
        {/* === Left Panel: Branding === */}
        <section
          className="lg:w-1/2 relative flex flex-col items-center justify-center p-8 sm:p-12 lg:p-16 overflow-hidden min-h-[260px]"
          style={{ background: 'linear-gradient(135deg, #FFF0E6 0%, #F5C49A 100%)' }}
        >
          {/* Decorative rings */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-30">
            <div className="w-80 h-80 rounded-full border-[2px]" style={{ borderColor: 'rgba(212,160,23,0.4)' }}>
              <div className="w-56 h-56 rounded-full border-[4px] m-auto mt-12" style={{ borderColor: 'rgba(212,160,23,0.5)' }}>
                <div className="w-36 h-36 rounded-full border-[8px] m-auto mt-8 flex items-center justify-center" style={{ borderColor: 'rgba(196,83,58,0.5)', backgroundColor: 'rgba(212,160,23,0.1)' }}>
                  <Icon name="face" size={64} style={{ color: '#C4533A' }} />
                </div>
              </div>
            </div>
          </div>

          <div className="relative z-10 text-center">
            <h1 className="text-6xl font-black mb-3" style={{ color: '#4A2B0F' }}>FDAS</h1>
            <p className="text-base font-semibold" style={{ color: '#8e4a01' }}>
              Automated Attendance. Zero Effort.
            </p>
          </div>

          <div className="relative z-10 text-center mt-auto pt-8">
            <p className="text-xs font-bold uppercase tracking-widest opacity-70" style={{ color: '#934619' }}>
              Govt. Islamia Graduate College, Gujranwala
            </p>
          </div>
        </section>

        {/* === Right Panel: Login Form === */}
        <section
          className="lg:w-1/2 flex items-center justify-center p-4 sm:p-8"
          style={{ backgroundColor: '#fff8f6' }}
        >
          <div
            className="w-full max-w-sm rounded-2xl p-6 sm:p-8 flex flex-col gap-6 border-t-4"
            style={{
              backgroundColor: '#ffffff',
              borderColor: '#D4A017',
              boxShadow: '0 8px 30px rgba(232,146,74,0.15)',
            }}
          >
            <header className="text-center">
              <h2 className="text-3xl font-bold" style={{ color: '#934619' }}>System Access</h2>
              <p className="text-sm mt-1" style={{ color: '#55433b' }}>Sign in to manage attendance</p>
            </header>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              {/* Username */}
              <div className="flex flex-col gap-1">
                <label htmlFor="email" className="text-xs font-bold ml-1" style={{ color: '#55433b' }}>
                  Email
                </label>
                <div className="relative flex items-center">
                  <Icon name="person" size={20} className="absolute left-3" style={{ color: '#ffc641' }} />
                  <input
                    id="email"
                    type="email"
                    value={form.email}
                    onChange={e => setForm({ ...form, email: e.target.value })}
                    placeholder="admin@fdas.local"
                    autoComplete="username"
                    className="fdas-input pl-10 pr-4"
                    style={{ borderColor: '#dbc1b7', color: '#4A2B0F', backgroundColor: '#ffffff' }}
                    onFocus={e => { e.target.style.borderColor = '#E8924A'; e.target.style.boxShadow = '0 0 0 3px rgba(232,146,74,0.15)' }}
                    onBlur={e => { e.target.style.borderColor = '#dbc1b7'; e.target.style.boxShadow = 'none' }}
                  />
                </div>
              </div>

              {/* Password */}
              <div className="flex flex-col gap-1">
                <label htmlFor="password" className="text-xs font-bold ml-1" style={{ color: '#55433b' }}>
                  Password
                </label>
                <div className="relative flex items-center">
                  <Icon name="lock" size={20} className="absolute left-3" style={{ color: '#ffc641' }} />
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={form.password}
                    onChange={e => setForm({ ...form, password: e.target.value })}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    className="fdas-input pl-10 pr-12"
                    style={{ borderColor: '#dbc1b7', color: '#4A2B0F', backgroundColor: '#ffffff' }}
                    onFocus={e => { e.target.style.borderColor = '#E8924A'; e.target.style.boxShadow = '0 0 0 3px rgba(232,146,74,0.15)' }}
                    onBlur={e => { e.target.style.borderColor = '#dbc1b7'; e.target.style.boxShadow = 'none' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 transition-colors"
                    style={{ color: '#934619' }}
                    aria-label="Toggle password visibility"
                    title={showPassword ? 'Hide password' : 'Show password'}
                  >
                    <Icon name={showPassword ? 'visibility' : 'visibility_off'} size={20} />
                  </button>
                </div>
              </div>

              {/* Remember + Forgot */}
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={e => setRemember(e.target.checked)}
                    className="w-4 h-4 rounded"
                    style={{ accentColor: '#934619' }}
                  />
                  <span className="text-xs" style={{ color: '#55433b' }}>Remember me</span>
                </label>
                <a href="#" className="text-xs underline underline-offset-2 transition-colors" style={{ color: '#934619' }}>
                  Forgot Password?
                </a>
              </div>

              {/* Error */}
              {error && (
                <div
                  className="flex items-start gap-2 p-3 rounded-xl border text-xs"
                  style={{ backgroundColor: '#ffdad6', borderColor: 'rgba(186,26,26,0.2)', color: '#93000a' }}
                >
                  <Icon name="error" size={16} className="flex-shrink-0 mt-0.5" />
                  <p>{error}</p>
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                className="fdas-button fdas-button-primary fdas-button-lg w-full"
                style={{
                  background: loading
                    ? '#887369'
                    : 'linear-gradient(135deg, #C4533A 0%, #934619 100%)',
                  boxShadow: '0 4px 15px rgba(196,83,58,0.3)',
                }}
              >
                {loading ? (
                  <>
                    <Icon name="settings" size={18} className="animate-spin" />
                    Signing in...
                  </>
                ) : (
                  <>
                    <Icon name="login" size={18} />
                    Sign In
                  </>
                )}
              </button>
            </form>

            <p className="text-center text-xs" style={{ color: '#55433b' }}>
              Need access?{' '}
              <Link to="/register" className="font-bold underline underline-offset-2" style={{ color: '#934619' }}>
                Request an account
              </Link>
            </p>

            {/* Demo hint */}
            <div className="text-center text-xs rounded-xl p-3" style={{ backgroundColor: '#fff1eb', color: '#55433b' }}>
              <p className="font-bold mb-1" style={{ color: '#887369' }}>Demo Credentials</p>
              <p>Admin: <span className="font-mono font-bold">admin@fdas.local / Admin@12345</span></p>
              <p>Operator: <span className="font-mono font-bold">operator.cs@fdas.local / Operator@12345</span></p>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
