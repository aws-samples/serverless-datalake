import React, { createContext, useContext, useReducer, useEffect, useRef } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import io from 'socket.io-client';

const ChatContext = createContext();

const initialState = {
  messages: [],
  isLoading: false,
  isConnected: false,
  error: null,
  availableTools: [],
  connectionStatus: 'disconnected', // 'connected', 'connecting', 'disconnected', 'reconnecting'
  mcpStatus: {},
  reconnectionAttempts: 0,
  maxReconnectionAttempts: 5,
};

function chatReducer(state, action) {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_CONNECTED':
      return { ...state, isConnected: action.payload };
    case 'SET_CONNECTION_STATUS':
      return { ...state, connectionStatus: action.payload };
    case 'SET_MCP_STATUS':
      return { ...state, mcpStatus: action.payload };
    case 'SET_RECONNECTION_ATTEMPTS':
      return { ...state, reconnectionAttempts: action.payload };
    case 'ADD_MESSAGE':
      return { 
        ...state, 
        messages: [...state.messages, action.payload],
        error: null 
      };
    case 'UPDATE_LAST_MESSAGE':
      return {
        ...state,
        messages: state.messages.map((msg, index) => 
          index === state.messages.length - 1 
            ? { 
                ...msg, 
                ...action.payload,
                // Accumulate thinking content
                thinking: action.payload.thinking !== undefined 
                  ? (msg.thinking || '') + action.payload.thinking
                  : msg.thinking,
                // For content, replace if it's final, accumulate if partial
                content: action.payload.content !== undefined 
                  ? (action.payload.is_partial ? (msg.content || '') + action.payload.content : action.payload.content)
                  : msg.content
              }
            : msg
        )
      };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'SET_TOOLS':
      return { ...state, availableTools: action.payload };
    case 'CLEAR_MESSAGES':
      return { ...state, messages: [] };
    default:
      return state;
  }
}

export function ChatProvider({ children }) {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const socketRef = useRef(null);
  const reconnectionTimeoutRef = useRef(null);
  const healthCheckIntervalRef = useRef(null);

  // Initialize WebSocket connection with enhanced reconnection
  useEffect(() => {
    connectWebSocket();
    startHealthCheck();

    // Cleanup on unmount
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      if (reconnectionTimeoutRef.current) {
        clearTimeout(reconnectionTimeoutRef.current);
      }
      if (healthCheckIntervalRef.current) {
        clearInterval(healthCheckIntervalRef.current);
      }
    };
  }, []); // Empty dependency array ensures this only runs once

  const connectWebSocket = () => {
    dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'connecting' });
    
    // Connect to WebSocket server with enhanced configuration
    socketRef.current = io('http://localhost:5001', {
      transports: ['websocket', 'polling'],
      timeout: 20000,
      reconnection: false, // We'll handle reconnection manually
      forceNew: true
    });

    // Connection event handlers
    socketRef.current.on('connect', () => {
      console.log('WebSocket connected');
      dispatch({ type: 'SET_CONNECTED', payload: true });
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'connected' });
      dispatch({ type: 'SET_RECONNECTION_ATTEMPTS', payload: 0 });
      
      // Test connection with ping
      socketRef.current.emit('ping');
      
      // Check MCP status after connection
      checkMCPStatus();
    });

    socketRef.current.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      dispatch({ type: 'SET_CONNECTED', payload: false });
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'disconnected' });
      
      // Attempt reconnection if not manually disconnected
      if (reason !== 'io client disconnect') {
        scheduleReconnection();
      }
    });

    socketRef.current.on('connected', (data) => {
      console.log('WebSocket connection confirmed:', data);
      dispatch({ type: 'SET_CONNECTED', payload: true });
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'connected' });
      
      if (data.status === 'error') {
        console.error('Connection error:', data.error);
        toast.error(`Connection error: ${data.error}`);
        scheduleReconnection();
      }
    });

    socketRef.current.on('pong', (data) => {
      console.log('WebSocket ping successful:', data);
    });

    socketRef.current.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      dispatch({ type: 'SET_CONNECTED', payload: false });
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'disconnected' });
      scheduleReconnection();
    });

    // Chat response event handler
    socketRef.current.on('chat_response', (data) => {
      handleChatResponse(data);
    });
  };

  const scheduleReconnection = () => {
    if (state.reconnectionAttempts >= state.maxReconnectionAttempts) {
      console.log('Max reconnection attempts reached');
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'disconnected' });
      toast.error('Connection lost. Please refresh the page or check your network.');
      return;
    }

    dispatch({ type: 'SET_CONNECTION_STATUS', payload: 'reconnecting' });
    dispatch({ type: 'SET_RECONNECTION_ATTEMPTS', payload: state.reconnectionAttempts + 1 });

    // Exponential backoff: 2^attempts * 1000ms, max 30 seconds
    const delay = Math.min(Math.pow(2, state.reconnectionAttempts) * 1000, 30000);
    
    console.log(`Scheduling reconnection attempt ${state.reconnectionAttempts + 1} in ${delay}ms`);
    
    reconnectionTimeoutRef.current = setTimeout(() => {
      console.log(`Attempting reconnection ${state.reconnectionAttempts + 1}/${state.maxReconnectionAttempts}`);
      
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      
      connectWebSocket();
    }, delay);
  };

  const startHealthCheck = () => {
    // Check MCP status every 30 seconds
    healthCheckIntervalRef.current = setInterval(() => {
      if (state.isConnected) {
        checkMCPStatus();
      }
    }, 30000);
  };

  const checkMCPStatus = async () => {
    try {
      const response = await axios.get('/api/mcp-status');
      dispatch({ type: 'SET_MCP_STATUS', payload: response.data });
      
      // Check if any MCP servers are disconnected
      const servers = response.data.servers || {};
      const disconnectedServers = Object.values(servers).filter(server => server.status !== 'connected');
      
      if (disconnectedServers.length > 0) {
        console.warn('Some MCP servers are disconnected:', disconnectedServers);
        // Optionally show a warning to the user
        if (disconnectedServers.length === Object.keys(servers).length) {
          toast.error('Not connected to MCP servers. Please ensure your servers are running.');
        }
      }
    } catch (error) {
      console.error('Failed to check MCP status:', error);
      dispatch({ type: 'SET_MCP_STATUS', payload: { error: error.message } });
    }
  };

  const forceReconnectMCP = async (mcpName = null) => {
    try {
      const response = await axios.post('/api/mcp-reconnect', {
        mcp_name: mcpName
      });
      
      toast.success(mcpName ? 
        `Reconnection attempted for ${mcpName}` : 
        'Reconnection attempted for all MCP servers'
      );
      
      // Refresh MCP status after reconnection attempt
      setTimeout(() => checkMCPStatus(), 2000);
      
      return response.data;
    } catch (error) {
      console.error('Failed to reconnect MCP servers:', error);
      toast.error('Failed to reconnect MCP servers');
      throw error;
    }
  };

  const manualReconnect = () => {
    dispatch({ type: 'SET_RECONNECTION_ATTEMPTS', payload: 0 });
    
    if (socketRef.current) {
      socketRef.current.disconnect();
    }
    
    connectWebSocket();
  };

  // Check connection status on mount
  useEffect(() => {
    checkConnection();
  }, []);

  const checkConnection = async () => {
    try {
      const response = await axios.get('/api/health');
      const isHealthy = response.data.status === 'healthy';
      dispatch({ type: 'SET_CONNECTED', payload: isHealthy });
      
      if (isHealthy) {
        checkMCPStatus();
      }
    } catch (error) {
      dispatch({ type: 'SET_CONNECTED', payload: false });
      console.error('Connection check failed:', error);
    }
  };

  const handleChatResponse = (data) => {
    switch (data.type) {
      case 'start':
        // Stream started
        break;
        
      case 'thinking':
        // Real-time thinking updates from the chatbot - accumulate thinking content
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            thinking: (data.content || ''),
            isLoading: true,
          }
        });
        break;
        
      case 'tool_use':
        // Tool usage information
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            toolUse: {
              tool: data.tool || 'Unknown Tool',
              input: data.input || '',
              timestamp: data.timestamp
            },
            isLoading: true,
          }
        });
        break;
        
      case 'content':
        if (data.is_partial) {
          // Update with partial content - accumulate
          dispatch({
            type: 'UPDATE_LAST_MESSAGE',
            payload: {
              content: data.content || '',
              is_partial: true,
              isLoading: true,
            }
          });
        } else {
          // Final content - replace content but preserve thinking
          dispatch({
            type: 'UPDATE_LAST_MESSAGE',
            payload: {
              content: data.content || '',
              is_partial: false,
              isLoading: false,
              // Don't clear thinking content, let it remain visible
            }
          });
          // Reset global loading state
          dispatch({ type: 'SET_LOADING', payload: false });
        }
        break;
        
      case 'data':
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            data: data.data,
            isLoading: false,
          }
        });
        dispatch({ type: 'SET_LOADING', payload: false });
        break;
        
      case 'chart':
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            chart: data.chart,
          }
        });
        break;
        
      case 'dashboard':
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            dashboard: data.content,
            dashboardMetadata: data.metadata,
            isLoading: false,
          }
        });
        // Reset global loading state
        dispatch({ type: 'SET_LOADING', payload: false });
        break;
        
      case 'html_content':
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            htmlContent: data.content,
            metadata: data.metadata,
            htmlContentTitle: data.title || "Analysis Report",
            isLoading: false,
          }
        });
        // Reset global loading state
        dispatch({ type: 'SET_LOADING', payload: false });
        break;
        
      case 'with_citations':
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            content: data.content || '',
            citations: data.citations,
            query: data.query,
            citationsTimestamp: data.timestamp,
            isLoading: false,
          }
        });
        // Reset global loading state
        dispatch({ type: 'SET_LOADING', payload: false });
        break;
        
      case 'dashboard_file':
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            dashboardFile: data.content,
            dashboardMetadata: data.metadata,
            isLoading: false,
          }
        });
        // Reset global loading state
        dispatch({ type: 'SET_LOADING', payload: false });
        break;

        case 'widget_file':
          dispatch({
            type: 'UPDATE_LAST_MESSAGE',
            payload: {
              widgetFile: data.content,
              widgetMetadata: data.metadata,
              isLoading: false,
            }
          });
          // Reset global loading state
          dispatch({ type: 'SET_LOADING', payload: false });
          break;
        
      case 'confirmation_needed':
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            needsConfirmation: true,
            plan: data.plan,
            originalQuery: data.original_query,
            isLoading: false,
          }
        });
        // Reset global loading state
        dispatch({ type: 'SET_LOADING', payload: false });
        break;
        
      case 'tool_approval_needed':
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            needsToolApproval: true,
            toolApprovalData: data, // Use data directly, not data.extra
            isLoading: false,
          }
        });
        // Reset global loading state
        dispatch({ type: 'SET_LOADING', payload: false });
        break;
        
      case 'error':
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            content: `Error: ${data.content}`,
            isLoading: false,
            error: true,
          }
        });
        // Reset global loading state
        dispatch({ type: 'SET_LOADING', payload: false });
        toast.error(data.content);
        break;
        
      case 'end':
        // Stream ended - preserve thinking content
        dispatch({
          type: 'UPDATE_LAST_MESSAGE',
          payload: {
            isLoading: false,
            // Don't clear thinking content
          }
        });
        // Reset global loading state
        dispatch({ type: 'SET_LOADING', payload: false });
        break;
        
      default:
        console.log('Unknown response type:', data.type);
    }
  };

  const sendMessage = async (message) => {
    if (!message.trim()) return;

    // Check connection before sending
    if (!state.isConnected || state.connectionStatus !== 'connected') {
      toast.error('Not connected to server. Attempting to reconnect...');
      manualReconnect();
      return;
    }

    // Prevent layout shifts by scrolling to top before adding messages
    window.scrollTo(0, 0);
    
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };

    dispatch({ type: 'ADD_MESSAGE', payload: userMessage });

    const assistantMessage = {
      id: Date.now() + 1,
      type: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isLoading: true,
    };

    dispatch({ type: 'ADD_MESSAGE', payload: assistantMessage });
    dispatch({ type: 'SET_LOADING', payload: true });

    try {
      // Send message via WebSocket
      if (socketRef.current && socketRef.current.connected) {
        socketRef.current.emit('chat_message', { message });
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.error('Error sending message:', error);
      dispatch({
        type: 'UPDATE_LAST_MESSAGE',
        payload: {
          content: 'Sorry, I encountered an error processing your request. Please try again.',
          isLoading: false,
          error: true,
        }
      });
      dispatch({ type: 'SET_LOADING', payload: false });
      toast.error('Failed to get response');
    }
  };

  const clearMessages = () => {
    dispatch({ type: 'CLEAR_MESSAGES' });
    dispatch({ type: 'SET_LOADING', payload: false });
  };

  const getAvailableTools = async () => {
    try {
      const response = await axios.get('/api/tools');
      dispatch({ type: 'SET_TOOLS', payload: response.data.tools });
    } catch (error) {
      console.error('Error fetching tools:', error);
    }
  };

  const confirmPlan = async (plan, original_query, is_single_widget=false) => {
    try {
      // Update the last message to show loading state
      dispatch({
        type: 'UPDATE_LAST_MESSAGE',
        payload: {
          needsConfirmation: false,
          isLoading: true,
          thinking: 'Executing confirmed plan...'
        }
      });
      
      // Send confirmation via WebSocket
      if (socketRef.current && socketRef.current.connected) {
        socketRef.current.emit('confirm_plan', {"plan": plan, "original_query": original_query, "is_single_widget": is_single_widget});
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.error('Error confirming plan:', error);
      dispatch({
        type: 'UPDATE_LAST_MESSAGE',
        payload: {
          content: 'Sorry, I encountered an error processing your confirmation. Please try again.',
          isLoading: false,
          error: true,
        }
      });
      dispatch({ type: 'SET_LOADING', payload: false });
      toast.error('Failed to confirm plan');
    }
  };
  
  const confirmToolApproval = async (approvalData, approvalResponse = 'approve') => {
    try {
      // Update the last message to show loading state
      dispatch({
        type: 'UPDATE_LAST_MESSAGE',
        payload: {
          needsToolApproval: false,
          isLoading: true,
          thinking: `Tool approval: ${approvalResponse}. Continuing execution...`
        }
      });
      
      // Handle both single interrupt (backward compatibility) and multiple interrupts
      const interrupts = approvalData.interrupts || [approvalData];
      const interruptIds = interrupts.map(interrupt => interrupt.interrupt_id || approvalData.interrupt_id);
      const approvalResponses = new Array(interrupts.length).fill(approvalResponse);
      
      // Send approval response via WebSocket
      if (socketRef.current && socketRef.current.connected) {
        socketRef.current.emit('tool_approval_response', {
          agent_name: approvalData.agent_name,
          query: approvalData.query,
          interrupt_ids: interruptIds, // Changed from interrupt_id to interrupt_ids (array)
          approval_responses: approvalResponses, // Changed from approval_response to approval_responses (array)
          pending_responses: approvalData.pending_responses || [],
          remaining_plan: approvalData.remaining_plan || [],
          original_query: approvalData.original_query || ''
        });
      } else {
        throw new Error('WebSocket not connected');
      }
    } catch (error) {
      console.error('Error sending tool approval:', error);
      dispatch({
        type: 'UPDATE_LAST_MESSAGE',
        payload: {
          content: 'Sorry, I encountered an error processing your approval. Please try again.',
          isLoading: false,
          error: true,
        }
      });
      dispatch({ type: 'SET_LOADING', payload: false });
      toast.error('Failed to send tool approval');
    }
  };
  
  const rejectToolApproval = async (approvalData) => {
    await confirmToolApproval(approvalData, 'deny');
  };

  const alwaysApproveToolApproval = async (approvalData) => {
    await confirmToolApproval(approvalData, 'always');
  };

  const rejectPlan = async (plan, original_query) => {
    // Update the last message to show rejection
    dispatch({
      type: 'UPDATE_LAST_MESSAGE',
      payload: {
        needsConfirmation: false,
        content: 'Plan rejected. Please try a different query or approach.',
        isLoading: false,
      }
    });
    dispatch({ type: 'SET_LOADING', payload: false });
  };

  const value = {
    ...state,
    sendMessage,
    clearMessages,
    getAvailableTools,
    checkConnection,
    checkMCPStatus,
    forceReconnectMCP,
    manualReconnect,
    socketRef,
    confirmPlan,
    rejectPlan,
    confirmToolApproval,
    rejectToolApproval,
    alwaysApproveToolApproval,
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
} 