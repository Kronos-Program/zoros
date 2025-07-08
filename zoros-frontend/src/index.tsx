// See architecture: docs/zoros_architecture.md#ui-blueprint
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ZorosStoreProvider } from './hooks/useZorosStore.js';
import { ThemeProvider } from './theme';
import './theme.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider>
      <ZorosStoreProvider>
        <App />
      </ZorosStoreProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
