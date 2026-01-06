/**
 * Socket.IO Tab Session Manager
 * 
 * This utility helps maintain separate Socket.IO sessions for different browser tabs
 * by generating and storing tab-specific IDs.
 */
import io from 'socket.io-client';

class TabSessionManager {
  constructor() {
    // Generate a unique ID for this tab if one doesn't exist
    this.tabId = localStorage.getItem('currentTabId');
    
    if (!this.tabId) {
      this.tabId = `tab_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
      localStorage.setItem('currentTabId', this.tabId);
    }
    
    // Handle tab/window close
    window.addEventListener('beforeunload', () => {
      localStorage.removeItem('currentTabId');
    });
  }
  
  /**
   * Get the tab-specific session ID
   * @returns {string} The unique tab ID
   */
  getTabId() {
    return this.tabId;
  }
  
  /**
   * Create a Socket.IO connection with the tab ID included
   * @param {string} url - The Socket.IO server URL
   * @param {object} options - Socket.IO connection options
   * @returns {SocketIO.Socket} The Socket.IO connection
   */
  connectSocket(url, options = {}) {
    // Add the tabId as a query parameter
    const connectionOptions = {
      ...options,
      query: {
        ...options.query,
        tabId: this.tabId
      }
    };
    
    // Connect to Socket.IO with the tab ID
    const socket = io(url, connectionOptions);
    
    return socket;
  }
}

// Export as a singleton
export const tabSessionManager = new TabSessionManager();