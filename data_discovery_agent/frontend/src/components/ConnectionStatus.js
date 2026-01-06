import React from 'react';
import { Wifi, WifiOff } from 'lucide-react';

function ConnectionStatus({ isConnected }) {
  return (
    <div className="flex items-center space-x-2">
      {isConnected ? (
        <>
          <Wifi className="h-4 w-4 text-green-500" />
          <span className="text-sm text-green-700">Connected</span>
        </>
      ) : (
        <>
          <WifiOff className="h-4 w-4 text-red-500" />
          <span className="text-sm text-red-700">Disconnected</span>
        </>
      )}
    </div>
  );
}

export default ConnectionStatus; 