import { getIdToken } from './auth';
import { getConfig } from '../config/config';

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface ProgressMessage {
  status: 'processing_started' | 'progress' | 'processing_complete' | 'error';
  docId: string;
  totalPages?: number;
  pagesProcessed?: number;
  errorCode?: string;
  message?: string;
  recoverable?: boolean;
}

export type MessageHandler = (message: ProgressMessage) => void;
export type StatusHandler = (status: WebSocketStatus) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private messageHandlers: Set<MessageHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isIntentionallyClosed = false;

  /**
   * Connect to the WebSocket API
   */
  async connect(): Promise<void> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    this.isIntentionallyClosed = false;

    try {
      // Get auth token for WebSocket connection
      const token = await getIdToken();
      const config = getConfig();
      const wsUrl = `${config.websocketUrl}?token=${encodeURIComponent(token)}`;

      this.updateStatus('connecting');
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.updateStatus('connected');
        
        // Generate a client-side connection ID for tracking
        // In a real AWS API Gateway WebSocket setup, this would be provided by AWS
        this.connectionId = `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        console.log('Generated connection ID:', this.connectionId);
      };

      this.ws.onmessage = (event) => {
        try {
          const message: ProgressMessage = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.updateStatus('error');
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        this.updateStatus('disconnected');
        
        // Attempt to reconnect if not intentionally closed
        if (!this.isIntentionallyClosed) {
          this.attemptReconnect();
        }
      };
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error);
      this.updateStatus('error');
      throw error;
    }
  }

  /**
   * Disconnect from the WebSocket
   */
  disconnect(): void {
    this.isIntentionallyClosed = true;
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.updateStatus('disconnected');
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.updateStatus('error');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.connect().catch((error) => {
        console.error('Reconnection failed:', error);
      });
    }, delay);
  }

  /**
   * Send a message through the WebSocket
   */
  send(message: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.error('WebSocket is not connected');
    }
  }

  /**
   * Subscribe to WebSocket messages
   */
  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    
    // Return unsubscribe function
    return () => {
      this.messageHandlers.delete(handler);
    };
  }

  /**
   * Subscribe to WebSocket status changes
   */
  onStatusChange(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    
    // Return unsubscribe function
    return () => {
      this.statusHandlers.delete(handler);
    };
  }

  /**
   * Handle incoming messages
   */
  private handleMessage(message: ProgressMessage): void {
    console.log('WebSocket message received:', message);
    
    this.messageHandlers.forEach((handler) => {
      try {
        handler(message);
      } catch (error) {
        console.error('Error in message handler:', error);
      }
    });
  }

  /**
   * Update connection status
   */
  private updateStatus(status: WebSocketStatus): void {
    this.statusHandlers.forEach((handler) => {
      try {
        handler(status);
      } catch (error) {
        console.error('Error in status handler:', error);
      }
    });
  }

  /**
   * Get current connection status
   */
  getStatus(): WebSocketStatus {
    if (!this.ws) return 'disconnected';
    
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      case WebSocket.CLOSING:
      case WebSocket.CLOSED:
        return 'disconnected';
      default:
        return 'disconnected';
    }
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Get the current WebSocket connection ID
   * For AWS API Gateway WebSocket, this needs to be obtained from the backend
   * or tracked when the connection is established
   */
  getConnectionId(): string | null {
    return this.connectionId;
  }

  /**
   * Set the connection ID (typically received from the backend)
   */
  setConnectionId(connectionId: string): void {
    this.connectionId = connectionId;
  }

  private connectionId: string | null = null;
}

// Export singleton instance
export const websocketService = new WebSocketService();

export default websocketService;
