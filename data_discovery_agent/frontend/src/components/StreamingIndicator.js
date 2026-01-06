import React from 'react';

function StreamingIndicator() {
  return (
    <div className="flex items-center space-x-1 text-gray-500">
      <span className="text-sm">Streaming</span>
      <div className="flex space-x-1">
        <div className="w-1 h-1 bg-gray-400 rounded-full animate-pulse" style={{ animationDelay: '0ms' }}></div>
        <div className="w-1 h-1 bg-gray-400 rounded-full animate-pulse" style={{ animationDelay: '150ms' }}></div>
        <div className="w-1 h-1 bg-gray-400 rounded-full animate-pulse" style={{ animationDelay: '300ms' }}></div>
      </div>
    </div>
  );
}

export default StreamingIndicator; 