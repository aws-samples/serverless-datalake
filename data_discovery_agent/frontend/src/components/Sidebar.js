import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  MessageSquare, 
  BarChart3, 
  BookOpenCheck,
  Settings, 
  Database, 
  Zap,
  Menu,
  X,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  History,
  Wifi,
  WifiOff,
  AlertCircle,
  CheckCircle,
  RotateCcw
} from 'lucide-react';
import axios from 'axios';
import { useChat } from '../contexts/ChatContext';
import toast from 'react-hot-toast';

function Sidebar({ sidebarOpen, setSidebarOpen, windowWidth }) {
  const location = useLocation();
  const [mcpServers, setMcpServers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const sidebarRef = useRef(null);
  
  // Get chat context for connection status and reconnection functions
  const { 
    isConnected, 
    connectionStatus, 
    mcpStatus, 
    reconnectionAttempts, 
    maxReconnectionAttempts,
    manualReconnect,
    forceReconnectMCP,
    checkMCPStatus 
  } = useChat();
  
  // Prevent sidebar position from changing when sending messages
  useEffect(() => {
    // Only apply fixed positioning on mobile
    if (windowWidth < 1024) { // lg breakpoint in Tailwind is 1024px
      if (sidebarOpen) {
        document.body.style.overflow = 'hidden';
      } else {
        document.body.style.overflow = '';
      }
    }
    
    return () => {
      document.body.style.overflow = '';
    };
  }, [sidebarOpen, windowWidth]);

  const navigation = [
    { name: 'Chat', href: '/chat', icon: MessageSquare },
    { name: 'Dashboard', href: '/dashboard', icon: BarChart3 },
    { name: 'Dashboard History', href: '/dashboard-history', icon: History },
    { name: 'Report History', href: '/report-history', icon: BookOpenCheck },
  ];

  // Fetch MCP server status
  const fetchMcpStatus = async () => {
    setIsLoading(true);
    try {
      const response = await axios.get('/api/mcp-status');
      const servers = response.data.servers;
      
      // Dynamically create server list from API response
      const serverList = Object.entries(servers).map(([serverId, serverData]) => {
        // Map server types to icons (you can extend this mapping as needed)
        const iconMap = {
          mysql: Database,
          opensearch: Zap,
          athena: Database,
          s3vectors: Zap,
          // Add more mappings as needed
          default: Database // fallback icon
        };
        
        return {
          id: serverId,
          name: serverData.name,
          status: serverData.status,
          icon: iconMap[serverId] || iconMap.default,
          mcp_url: serverData.mcp_url,
          mcp_command: serverData.mcp_command,
          reconnection_attempts: serverData.reconnection_attempts || 0,
          max_attempts_reached: serverData.max_attempts_reached || false
        };
      });
      
      setMcpServers(serverList);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to fetch MCP status:', error);
      // Set empty array as fallback when API fails
      setMcpServers([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle WebSocket reconnection
  const handleWebSocketReconnect = () => {
    toast.loading('Attempting to reconnect...', { id: 'reconnect' });
    manualReconnect();
    setTimeout(() => {
      toast.dismiss('reconnect');
    }, 3000);
  };

  // Handle MCP server reconnection
  const handleMCPReconnect = async (mcpName = null) => {
    try {
      await forceReconnectMCP(mcpName);
      // Refresh status after reconnection attempt
      setTimeout(() => fetchMcpStatus(), 2000);
    } catch (error) {
      console.error('Failed to reconnect MCP:', error);
    }
  };

  // Handle refresh MCP status
  const handleRefreshMCPStatus = async () => {
    try {
      await checkMCPStatus();
      await fetchMcpStatus();
      toast.success('MCP status refreshed');
    } catch (error) {
      toast.error('Failed to refresh MCP status');
    }
  };

  // Get connection status color and icon
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

  // Fetch status on component mount and every 30 seconds
  useEffect(() => {
    fetchMcpStatus();
    const interval = setInterval(fetchMcpStatus, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div 
        ref={sidebarRef}
        className={`
        fixed inset-y-0 left-0 z-50 bg-white shadow-xl transform transition-all duration-300 ease-in-out flex flex-col overflow-hidden border-r border-detective-200
        ${sidebarOpen ? 'w-64 translate-x-0' : 'w-16 translate-x-0'}
        lg:static lg:inset-0 lg:translate-y-0
      `}>
        <div className="flex items-center justify-between h-16 px-4 border-b border-detective-200 bg-white">
          <div className="flex items-center">
            <div className="flex-shrink-0 flex items-center">
              <div className="h-8 w-8 bg-detective-accent rounded-lg flex items-center justify-center mr-3">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 12l2 2 4-4"/>
                  <path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"/>
                  <path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"/>
                  <path d="M12 3c0 1-1 3-3 3s-3-2-3-3 1-3 3-3 3 2 3 3"/>
                  <path d="M12 21c0-1-1-3-3-3s-3 2-3 3 1 3 3 3 3-2 3-3"/>
                </svg>
              </div>
              <div className={`transition-opacity duration-300 ${
                sidebarOpen ? 'opacity-100' : 'opacity-0'
              }`}>
                <h1 className="text-xl font-semibold text-detective-900">
                  DataDiscovery Agent
                </h1>
                <p className="text-xs text-detective-500 -mt-1">
                  Intelligent Data Analytics Platform
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {/* Mobile close button */}
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden p-2 rounded-md text-detective-500 hover:text-detective-700 hover:bg-detective-100"
            >
              <X className="h-6 w-6" />
            </button>
          </div>
        </div>

        <div className={`flex flex-col min-h-0 ${sidebarOpen ? 'overflow-y-auto' : 'overflow-hidden'}`}>
          {/* Navigation */}
          <nav className="px-3 py-4 space-y-2">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`
                    group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200
                    ${isActive 
                      ? 'bg-detective-accent text-white shadow-sm' 
                      : 'text-detective-600 hover:bg-detective-100 hover:text-detective-800'
                    }
                  `}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSidebarOpen(false);
                  }}
                  title={!sidebarOpen ? item.name : ''}
                >
                  <item.icon className={`
                    h-5 w-5 flex-shrink-0
                    ${sidebarOpen ? 'mr-3' : 'mx-auto'}
                    ${isActive ? 'text-white' : 'text-detective-500 group-hover:text-detective-600'}
                  `} />
                  <span className={`transition-opacity duration-300 ${
                    sidebarOpen ? 'opacity-100' : 'opacity-0'
                  }`}>
                    {item.name}
                  </span>
                </Link>
              );
            })}
          </nav>

          {/* Connection Status & MCP Server Management */}
          <div className={`border-t border-detective-200 transition-all duration-300 bg-detective-50 ${
            sidebarOpen ? 'p-4' : 'p-2'
          }`}>
            
            {/* WebSocket Connection Status */}
            {sidebarOpen && (
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-detective-600 uppercase tracking-wider">
                    Connection
                  </h3>
                  <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {(() => {
                      const { color, icon: StatusIcon, text } = getConnectionStatusDisplay();
                      return (
                        <>
                          <StatusIcon className={`w-4 h-4 ${color} ${connectionStatus === 'connecting' || connectionStatus === 'reconnecting' ? 'animate-spin' : ''}`} />
                          <span className={`text-sm ${color}`}>{text}</span>
                        </>
                      );
                    })()}
                  </div>
                  
                  {!isConnected && connectionStatus !== 'connecting' && connectionStatus !== 'reconnecting' && (
                    <button
                      onClick={handleWebSocketReconnect}
                      className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
                      title="Reconnect WebSocket"
                    >
                      Reconnect
                    </button>
                  )}
                </div>
              </div>
            )}
            
            {/* MCP Servers Section */}
            {sidebarOpen && (
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold text-detective-600 uppercase tracking-wider">
                  MCP Servers
                </h3>
                <button
                  onClick={handleRefreshMCPStatus}
                  disabled={isLoading}
                  className="p-1.5 rounded-md text-detective-500 hover:text-detective-700 hover:bg-detective-100 disabled:opacity-50"
                  title="Refresh MCP status"
                >
                  <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>
            )}
            
            {!sidebarOpen && (
              <div className="flex justify-center mb-2">
                <button
                  onClick={handleRefreshMCPStatus}
                  disabled={isLoading}
                  className="p-1.5 rounded-md text-detective-500 hover:text-detective-700 hover:bg-detective-100 disabled:opacity-50"
                  title="Refresh MCP status"
                >
                  <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>
            )}
            
            <div className="space-y-2">
              {mcpServers.map((server) => (
                <div key={server.id} className={`${
                  sidebarOpen ? 'bg-white rounded-lg p-3 border border-detective-200' : 'flex justify-center'
                }`}>
                  {sidebarOpen ? (
                    <div className="space-y-2">
                      {/* Header row with icon, name, and status indicator */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2 min-w-0 flex-1">
                          <server.icon className="h-4 w-4 text-detective-accent flex-shrink-0" />
                          <span className="text-sm text-detective-700 font-medium truncate">{server.name}</span>
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            server.status === 'connected' ? 'bg-green-500' : 
                            server.status === 'disconnected' ? 'bg-red-500' :
                            server.status === 'not_initialized' ? 'bg-gray-400' :
                            'bg-yellow-500'
                          }`}></div>
                        </div>
                      </div>
                      
                      {/* URL/Command row */}
                      <div className="text-xs text-detective-500 truncate">
                        {server.mcp_url || server.mcp_command || 'No URL/Command'}
                        {server.reconnection_attempts > 0 && (
                          <span className="text-orange-600 ml-1">
                            ({server.reconnection_attempts} attempts)
                          </span>
                        )}
                        {server.disabled && (
                          <span className="text-gray-500 ml-1">(Disabled)</span>
                        )}
                      </div>
                      
                      {/* Status and action buttons row */}
                      <div className="flex items-center justify-between space-x-2">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ${
                          server.status === 'connected' ? 'bg-green-100 text-green-700' : 
                          server.status === 'disconnected' ? 'bg-red-100 text-red-700' :
                          server.status === 'not_initialized' ? 'bg-gray-100 text-gray-700' :
                          'bg-yellow-100 text-yellow-700'
                        }`}>
                          {server.status === 'connected' ? 'Connected' : 
                           server.status === 'disconnected' ? 'Disconnected' :
                           server.status === 'not_initialized' ? 'Not Initialized' :
                           server.status}
                        </span>
                        
                        {!server.disabled && (
                          <div className="flex space-x-1">
                            {server.status === 'not_initialized' && (
                              <button
                                onClick={() => handleMCPReconnect(server.id)}
                                className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors flex-shrink-0"
                                title={`Initialize ${server.name}`}
                              >
                                Init
                              </button>
                            )}
                            
                            {server.status === 'disconnected' && !server.max_attempts_reached && (
                              <button
                                onClick={() => handleMCPReconnect(server.id)}
                                className="px-2 py-0.5 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200 transition-colors flex-shrink-0"
                                title={`Reconnect ${server.name}`}
                              >
                                Reconnect
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex justify-center">
                      <server.icon className="h-4 w-4 text-detective-accent mx-auto" />
                    </div>
                  )}
                </div>
              ))}
            </div>
            
            {/* Global MCP Reconnect Button */}
            {sidebarOpen && mcpServers.some(server => server.status !== 'connected') && (
              <div className="mt-3 pt-2 border-t border-detective-200">
                <button
                  onClick={() => handleMCPReconnect()}
                  className="w-full px-3 py-2 text-xs bg-orange-500 text-white rounded hover:bg-orange-600 transition-colors"
                >
                  Reconnect All MCP Servers
                </button>
              </div>
            )}
            
            {sidebarOpen && lastUpdated && (
              <div className="mt-3 text-xs text-detective-500">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </div>
            )}
            
            {/* Error State */}
            {sidebarOpen && mcpStatus?.error && (
              <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                Error: {mcpStatus.error}
              </div>
            )}
          </div>

          {/* Settings */}
          <div className={`border-t border-detective-200 transition-all duration-300 bg-white ${
            sidebarOpen ? 'p-4' : 'p-2'
          }`}>
            
            {/* Toggle sidebar button at bottom */}
            <div className="mt-4 flex bg-white" style={{"justify-content":"right"}}>
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2 rounded-lg text-detective-500 hover:bg-detective-100 hover:text-detective-700 transition-colors"
                title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
              >
                {sidebarOpen ? <ChevronLeft className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile menu button */}
      <div className="lg:hidden fixed top-4 left-4 z-50">
        <button
          onClick={() => setSidebarOpen(true)}
          className="p-2 rounded-lg text-detective-600 hover:text-detective-800 bg-white shadow-lg border border-detective-200"
        >
          <Menu className="h-6 w-6" />
        </button>
      </div>


    </>
  );
}

export default Sidebar; 