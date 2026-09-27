import { Link } from 'react-router-dom'
import Icon from './Icon'

export default function AuthRecoveryShell({ title, description, icon = 'lock', children }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-6" style={{ backgroundColor: '#FAF4EC' }}>
      <main className="w-full max-w-lg overflow-hidden rounded-2xl border-t-4" style={{ backgroundColor: '#fff8f6', borderColor: '#D4A017', boxShadow: '0 8px 40px rgba(232,146,74,0.2)' }}>
        <section className="p-6 sm:p-8 md:p-10">
          <header className="mb-7 text-center">
            <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full" style={{ backgroundColor: '#FFF0E6', color: '#C4533A' }}>
              <Icon name={icon} size={30} />
            </div>
            <p className="text-xs font-bold uppercase tracking-widest" style={{ color: '#C4533A' }}>FDAS Account Security</p>
            <h1 className="mt-1 text-3xl font-black" style={{ color: '#4A2B0F' }}>{title}</h1>
            <p className="mt-2 text-sm leading-6" style={{ color: '#55433b' }}>{description}</p>
          </header>
          {children}
          <p className="mt-6 text-center text-sm" style={{ color: '#55433b' }}>
            <Link to="/login" className="font-bold underline underline-offset-2" style={{ color: '#934619' }}>Back to Sign In</Link>
          </p>
        </section>
      </main>
    </div>
  )
}
