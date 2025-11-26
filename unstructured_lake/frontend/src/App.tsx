import { Routes, Route, Navigate } from 'react-router-dom';
import { Authenticator } from '@aws-amplify/ui-react';
import { HomePage } from './pages/HomePage';
import { InsightsPage } from './pages/InsightsPage';
import { ImageInsightsPage } from './pages/ImageInsightsPage';

function App() {
  return (
    <Authenticator
      components={{
        SignIn: {
          Footer() {
            return (
              <div style={{ textAlign: 'center', marginTop: '1rem', padding: '1rem', backgroundColor: '#f9f9f9', borderRadius: '4px' }}>
                <p style={{ fontSize: '0.9rem', color: '#666', margin: '0 0 0.5rem 0' }}>
                  <strong>Seeing "There is already a signed in user" error?</strong>
                </p>
                <button
                  type="button"
                  onClick={() => {
                    // Use the global clearAuthState function
                    if ((window as any).clearAuthState) {
                      (window as any).clearAuthState();
                    } else {
                      // Fallback method
                      localStorage.clear();
                      sessionStorage.clear();
                      window.location.reload();
                    }
                  }}
                  style={{
                    backgroundColor: '#0073bb',
                    color: 'white',
                    border: 'none',
                    padding: '8px 16px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontSize: '0.9rem'
                  }}
                >
                  Clear Session & Reload
                </button>
                <p style={{ fontSize: '0.8rem', color: '#888', margin: '0.5rem 0 0 0' }}>
                  This will sign you out and refresh the page
                </p>
              </div>
            );
          }
        }
      }}
    >
      {({ user }) => {
        if (!user) {
          return <div>Loading...</div>;
        }
        
        return (
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/insights" element={<InsightsPage />} />
            <Route path="/image-insights" element={<ImageInsightsPage />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        );
      }}
    </Authenticator>
  );
}

export default App;
