import React from 'react';
import { useChat } from '../contexts/ChatContext';
import { 
  CheckCircle, 
  AlertCircle, 
  RefreshCw, 
  RotateCcw,
  WifiOff 
} from 'lucide-react';

/**
 * Simple connection status indicator component
 * Note: Full connection management is now integrated into the Sidebar component
 */
const ConnectionStatus = ({ showLabel = true, size = 'sm' }) => {
  const { 
    isConnected, 
    connectionStatus, 
    reconnectionAttempts, 
    maxReconnectionAttempts 
  } = useChat();

  const getConnectionStatusDisplay = () => {
    switch (connectionStatus) {
      case 'connected':
        return { color: 'text-green-600', icon: CheckCircle, text: 'Connected' };
      case 'connecting':
        return { color: 'text-yellow-600', icon: RefreshCw, text: 'Connecting...' };
      case 'reconnecting':
        return { color: 'text-orange-600', icon: RotateCcw, text: `Reconnecting... (${reconnectionAttempts}/${maxReconnectionAttempts})` };
      case 'disconnected':
        return { color: 'text-red-600', icon: AlertCircle, text: 'Disconnected' };
      default:
        return { color: 'text-gray-600', icon: WifiOff, text: 'Unknown' };
    }
  };

  const { color, icon: StatusIcon, text } = getConnectionStatusDisplay();
  const iconSize = size === 'sm' ? 'w-4 h-4' : 'w-5 h-5';
  const textSize = size === 'sm' ? 'text-sm' : 'text-base';

  return (
    <div className="flex items-center space-x-2">
      <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
      <StatusIcon className={`${iconSize} ${color} ${
        connectionStatus === 'connecting' || connectionStatus === 'reconnecting' ? 'animate-spin' : ''
      }`} />
      {showLabel && (
        <span className={`${textSize} ${color} font-medium`}>
          {text}
        </span>
      )}
    </div>
  );
};

export default ConnectionStatus;