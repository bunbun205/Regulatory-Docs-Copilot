import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import SettingsProvider from './app/SettingsProvider'
import './styles/tokens.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter><SettingsProvider><App /></SettingsProvider></BrowserRouter>
  </StrictMode>,
)
