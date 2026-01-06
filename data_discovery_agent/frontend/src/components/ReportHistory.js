import React, { useState, useEffect } from 'react';
import { Calendar, FileText, Loader2, ChevronDown } from 'lucide-react';
import axios from 'axios';

function ReportHistory() {
  const [dashboards, setDashboards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDashboard, setSelectedDashboard] = useState(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [dashboardContent, setDashboardContent] = useState('');

  useEffect(() => {
    fetchDashboards();
  }, []);

  const fetchDashboards = async () => {
    try {
      const response = await axios.get('/api/reports/history');
      setDashboards(response.data.reports);
    } catch (err) {
      setError('Failed to load dashboard history');
    } finally {
      setLoading(false);
    }
  };

  const loadDashboard = async (filename) => {
    try {
      setSelectedDashboard(filename);
      const response = await axios.get(`/api/report/${filename}`);
      setDashboardContent(response.data);
    } catch (err) {
      setError('Failed to load dashboard');
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const formatSize = (bytes) => {
    return (bytes / 1024).toFixed(1) + ' KB';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
        <span className="ml-2">Loading report history...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg p-4">
        {error}
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="bg-detective-800 p-4 rounded-lg shadow-lg mb-6 flex items-center">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-detective-accent mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="10" cy="10" r="7" />
          <line x1="21" y1="21" x2="15" y2="15" />
        </svg>
        <h1 className="text-2xl font-bold text-white">Investigation Reports</h1>
      </div>
      
      {/* Dashboard Dropdown */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-2">Select Report</h2>
        {dashboards.length === 0 ? (
          <p className="text-gray-500">No Reports generated yet.</p>
        ) : (
          <div className="relative">
            <div 
              className="p-3 border rounded-lg cursor-pointer hover:bg-gray-50 flex items-center justify-between"
              onClick={() => setDropdownOpen(!dropdownOpen)}
            >
              <div className="flex items-center space-x-2">
                <FileText className="h-4 w-4 text-gray-500" />
                <span className="font-medium">
                  {selectedDashboard ? selectedDashboard.replace('.html', '') : 'Select a dashboard'}
                </span>
              </div>
              <ChevronDown className={`h-4 w-4 transition-transform ${dropdownOpen ? 'transform rotate-180' : ''}`} />
            </div>
            
            {dropdownOpen && (
              <div className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
                {dashboards.map((dashboard) => (
                  <div
                    key={dashboard.filename}
                    className={`p-3 cursor-pointer hover:bg-gray-50 ${selectedDashboard === dashboard.filename ? 'bg-blue-50' : ''}`}
                    onClick={() => {
                      loadDashboard(dashboard.filename);
                      setDropdownOpen(false);
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm truncate">
                        {dashboard.filename.split('_')[0]}
                      </span>
                      <div className="flex items-center space-x-2 text-xs text-gray-500">
                        <span>{formatDate(dashboard.created_at)}</span>
                        <span>{formatSize(dashboard.size)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Dashboard Preview */}
      <div className="w-full">
          {selectedDashboard ? (
            <div>
              <h2 className="text-lg font-semibold mb-4">Report Preview</h2>
              <iframe
                srcDoc={dashboardContent}
                title="Dashboard Preview"
                className="border border-gray-200 rounded-lg overflow-hidden bg-white w-full"
                style={{ height: '600px' }}
                sandbox="allow-scripts allow-same-origin"
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 border border-gray-200 rounded-lg bg-gray-50">
              <p className="text-gray-500">Select a report to preview</p>
            </div>
          )}
        </div>
    </div>
  );
}

export default ReportHistory;