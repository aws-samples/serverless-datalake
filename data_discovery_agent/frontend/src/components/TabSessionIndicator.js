import React from 'react';
import { tabSessionManager } from '../utils/TabSessionManager';

function TabSessionIndicator() {
  return (
    <div className="text-xs text-gray-500 flex items-center">
      <span className="inline-block w-2 h-2 bg-blue-500 rounded-full mr-1"></span>
      Tab ID: {tabSessionManager.getTabId().split('_').pop()}
    </div>
  );
}

export default TabSessionIndicator;