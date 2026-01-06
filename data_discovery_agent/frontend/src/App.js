import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import Dashboard from './components/Dashboard';
import DashboardHistory from './components/DashboardHistory';
import { ChatProvider } from './contexts/ChatContext';
import { DashboardProvider } from './contexts/DashboardContext';
import ReportHistory from './components/ReportHistory';

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true); // Start expanded on desktop
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);
  
  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <Router>
      <ChatProvider>
        <DashboardProvider>
          <div className="h-screen flex bg-detective-paper">
            <Sidebar 
              sidebarOpen={sidebarOpen} 
              setSidebarOpen={setSidebarOpen} 
              windowWidth={windowWidth}
            />
            
            <div className={`flex-1 overflow-auto focus:outline-none transition-all duration-300`}>
              <Routes>
                <Route path="/" element={<Navigate to="/chat" replace />} />
                <Route path="/chat" element={<ChatInterface />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/dashboard-history" element={<DashboardHistory />} />
                <Route path="/report-history" element={<ReportHistory />} />
              </Routes>
            </div>
          </div>
          
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#f8f9fa',
                color: '#212529',
                border: '1px solid #dee2e6',
              },
            }}
          />
        </DashboardProvider>
      </ChatProvider>
    </Router>
  );
}

export default App; 