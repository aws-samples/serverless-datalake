import React, { useState } from 'react';
import { X, RefreshCw, Clock } from 'lucide-react';

function DashboardSettings({ isOpen, onClose, refreshInterval, onRefreshIntervalChange }) {
  const [localRefreshInterval, setLocalRefreshInterval] = useState(refreshInterval);

  const handleSave = () => {
    onRefreshIntervalChange(localRefreshInterval);
    onClose();
  };

  const handleCancel = () => {
    setLocalRefreshInterval(refreshInterval);
    onClose();
  };

  if (!isOpen) return null;

  const refreshOptions = [
    { value: 0, label: 'Manual refresh only' },
    { value: 10000, label: '10 seconds' },
    { value: 30000, label: '30 seconds' },
    { value: 60000, label: '1 minute' },
    { value: 300000, label: '5 minutes' },
    { value: 600000, label: '10 minutes' },
  ];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={handleCancel} />
        
        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
          <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">
                Dashboard Settings
              </h3>
              <button
                onClick={handleCancel}
                className="text-gray-400 hover:text-gray-500"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            <div className="space-y-6">
              {/* Auto-refresh Settings */}
              <div>
                <div className="flex items-center mb-3">
                  <RefreshCw className="h-5 w-5 text-gray-400 mr-2" />
                  <h4 className="text-sm font-medium text-gray-900">Auto-refresh Settings</h4>
                </div>
                
                <div className="space-y-3">
                  <label className="block text-sm font-medium text-gray-700">
                    Refresh Interval
                  </label>
                  <select
                    value={localRefreshInterval}
                    onChange={(e) => setLocalRefreshInterval(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    {refreshOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  
                  <p className="text-xs text-gray-500">
                    {localRefreshInterval === 0 
                      ? 'Widgets will only refresh when you manually click the refresh button.'
                      : `Widgets will automatically refresh every ${localRefreshInterval / 1000} seconds.`
                    }
                  </p>
                </div>
              </div>

              {/* Performance Info */}
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center mb-2">
                  <Clock className="h-4 w-4 text-gray-400 mr-2" />
                  <h4 className="text-sm font-medium text-gray-900">Performance</h4>
                </div>
                <p className="text-xs text-gray-600">
                  More frequent refreshes may impact performance. Consider using manual refresh for large datasets.
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
            <button
              onClick={handleSave}
              className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-primary-600 text-base font-medium text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 sm:ml-3 sm:w-auto sm:text-sm"
            >
              Save Settings
            </button>
            <button
              onClick={handleCancel}
              className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DashboardSettings; 