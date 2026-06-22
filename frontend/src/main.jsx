import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';

// Roboto self-hosted via @fontsource (DSGVO, kein Google-CDN).
import '@fontsource/roboto/300.css';
import '@fontsource/roboto/400.css';
import '@fontsource/roboto/500.css';
import '@fontsource/roboto/700.css';
import '@fontsource/roboto/900.css';

import './index.css';
import App from './App.jsx';
import { AuthProvider } from './auth/AuthContext.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#1d1d1b',
              color: '#ffffff',
              fontFamily: 'Roboto, sans-serif',
              borderRadius: '12px',
              padding: '12px 16px',
              fontSize: '14px',
            },
            success: { iconTheme: { primary: '#00a984', secondary: '#1d1d1b' } },
            error: {
              style: {
                background: '#dc2626',
                color: '#ffffff',
                fontFamily: 'Roboto, sans-serif',
                borderRadius: '12px',
                padding: '12px 16px',
                fontSize: '14px',
              },
            },
          }}
        />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
