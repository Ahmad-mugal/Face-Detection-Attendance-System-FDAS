import { Component } from 'react'

export default class ErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    if (import.meta.env.DEV) {
      console.error('Unexpected React error:', error, errorInfo)
    }
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <main
        className="min-h-screen flex items-center justify-center p-6"
        style={{ backgroundColor: '#FAF4EC' }}
      >
        <section
          className="w-full max-w-md rounded-2xl border-t-4 p-8 text-center"
          style={{ backgroundColor: '#ffffff', borderColor: '#C4533A', boxShadow: '0 8px 30px rgba(232,146,74,0.15)' }}
        >
          <h1 className="text-3xl font-black" style={{ color: '#4A2B0F' }}>Something went wrong.</h1>
          <p className="mt-3 text-sm" style={{ color: '#55433b' }}>Please reload the application.</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-6 rounded-xl px-5 py-3 text-sm font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #C4533A 0%, #934619 100%)' }}
          >
            Reload Application
          </button>
        </section>
      </main>
    )
  }
}
