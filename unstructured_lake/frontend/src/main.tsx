import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Amplify } from 'aws-amplify'
import { loadConfig } from './config/config'
import './utils/authUtils' // Import auth utilities for global access
import '@cloudscape-design/global-styles/index.css'
import '@aws-amplify/ui-react/styles.css'
import './index.css'
import App from './App.tsx'

// Initialize app after Amplify is configured
async function initializeApp() {
  try {
    console.log('Loading configuration...')
    const config = await loadConfig()
    
    console.log('Configuring Amplify...')
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: config.userPoolId,
          userPoolClientId: config.clientId,
        },
      },
    })
    
    console.log('Amplify configured successfully, rendering app...')
    
    // Render app only after Amplify is configured
    createRoot(document.getElementById('root')!).render(
      <StrictMode>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </StrictMode>,
    )
    
  } catch (error) {
    console.error('Failed to initialize app:', error)
    
    // Show error message to user
    const root = document.getElementById('root')!
    root.innerHTML = `
      <div style="display: flex; justify-content: center; align-items: center; height: 100vh; font-family: Arial, sans-serif;">
        <div style="text-align: center; padding: 2rem; border: 1px solid #ccc; border-radius: 8px;">
          <h2 style="color: #d32f2f;">Configuration Error</h2>
          <p>Failed to load application configuration.</p>
          <p style="font-size: 0.9rem; color: #666;">Please check the console for details.</p>
          <button onclick="window.location.reload()" style="margin-top: 1rem; padding: 0.5rem 1rem; background: #1976d2; color: white; border: none; border-radius: 4px; cursor: pointer;">
            Retry
          </button>
        </div>
      </div>
    `
  }
}

// Initialize the app
initializeApp()
