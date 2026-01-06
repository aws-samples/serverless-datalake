import React, { createContext, useContext, useReducer, useEffect, useRef } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import io from 'socket.io-client';
import { tabSessionManager } from '../utils/TabSessionManager';

const ChatContext = createContext();

const initialState = {
  messages: [],
  isLoading: false,
  isConnected: false,
  error: null,
  availableTools: [],
};

function chatReducer(state, action) {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_CONNECTED':
      return { ...state, isConnected: action.payload };
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

  // Initialize WebSocket connection
  useEffect(() => {
    // Connect to WebSocket server using the tab session manager
    socketRef.current = tabSessionManager.connectSocket('http://localhost:5000', {
      transports: ['websocket', 'polling'],
      timeout: 20000,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000
    });

    // Connection event handlers
    socketRef.current.on('connect', () => {
      console.log('WebSocket connected');
      dispatch({ type: 'SET_CONNECTED', payload: true });
      
      // Test connection with ping
      socketRef.current.emit('ping');
    });

    socketRef.current.on('disconnect', () => {
      console.log('WebSocket disconnected');
      dispatch({ type: 'SET_CONNECTED', payload: false });
    });

    socketRef.current.on('connected', (data) => {
      console.log('WebSocket connection confirmed:', data);
      console.log('Tab ID:', data.tabId || 'Not provided');
      dispatch({ type: 'SET_CONNECTED', payload: true });
    });

    socketRef.current.on('pong', (data) => {
      console.log('WebSocket ping successful:', data);
    });

    socketRef.current.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      dispatch({ type: 'SET_CONNECTED', payload: false });
    });

    // Chat response event handler
    socketRef.current.on('chat_response', (data) => {
      handleChatResponse(data);
    });

    // Cleanup on unmount
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []);

  // Check connection status on mount
  useEffect(() => {
    checkConnection();
  }, []);

  const checkConnection = async () => {
    try {
      const response = await axios.get('/api/health');
      dispatch({ type: 'SET_CONNECTED', payload: response.data.status === 'ok' });
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
    socketRef,
    confirmPlan,
    rejectPlan,
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