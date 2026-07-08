import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { AttendanceSessionProvider } from './context/AttendanceSessionContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AttendanceSessionProvider>
        <App />
      </AttendanceSessionProvider>
    </BrowserRouter>
  </StrictMode>,
)
