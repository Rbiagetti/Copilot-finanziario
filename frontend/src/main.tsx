import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import AppInitializer from "./AppInitializer";
import { startKeepAlive } from './utils/keepAlive'

startKeepAlive()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AppInitializer>
        <App />
      </AppInitializer>
    </BrowserRouter>
  </StrictMode>,
)
