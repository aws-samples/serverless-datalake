import React, { useState, useRef, useEffect } from 'react';
import { useChat } from '../contexts/ChatContext';
import { Send, Trash2, Bot, User, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ChatMessage from './ChatMessage';
import ConnectionStatus from './ConnectionStatus';
import TabSessionIndicator from './TabSessionIndicator';
import SherlockAvatar from './SherlockAvatar';
import CaseFileText from './CaseFileText';

function ChatInterface() {
  const { 
    messages, 
    isLoading, 
    isConnected, 
    sendMessage, 
    clearMessages,
    availableTools,
    checkConnection,
    socketRef 
  } = useChat();
  
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Focus input on mount
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const message = inputValue.trim();
    setInputValue('');
    setIsTyping(true);

    try {
      await sendMessage(message);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };
  
  const handleClearChat = () => {
    // Clear messages in the state
    clearMessages();
    
    // Access the socket reference directly from the destructured props
    const { current: socket } = socketRef;
    
    // Disconnect the websocket if it exists
    if (socket) {
      socket.disconnect();
      
      // Reconnect after a short delay
      setTimeout(() => {
        socket.connect();
        checkConnection();
      }, 500);
    }
  };

  const exampleQueries = [
    "Investigate all tables in the MySQL database",
    "Which devices are currently online ?",
    "Give me a status report on dispensers across all sites",
    "How many records are in the products table? I need evidence.",
    "Give me all data points on serverless-rag-demo repo under aws-samples org on Github",
    "Create a detailed report of the MySQL database structure",
    "What are the top 10 products by sales? Look for anomalies.",
    "Analyze the connection between users and their purchase history"
  ];

  return (
    <div className="flex flex-col h-full bg-detective-paper bg-detective-pattern">
      {/* Header */}
      <div className="detective-header px-3 py-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className="mr-3 text-detective-accent">
              <SherlockAvatar className="h-10 w-10" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">MCP Data Detective</h1>
              <p className="text-sm text-gray-300">
                Analyze multiple data sources. Uncover hidden insights.
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <TabSessionIndicator />
            <ConnectionStatus isConnected={isConnected} />
            <button
              onClick={handleClearChat}
              className="flex items-center px-3 py-2 text-sm font-medium text-detective-900 bg-detective-accent border border-detective-accent/50 rounded-md hover:bg-detective-accent/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-detective-accent"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Clear Chat
            </button>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 bg-detective-paper/80">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-20 h-20 bg-detective-accent/20 rounded-full flex items-center justify-center mb-4">
              <SherlockAvatar className="h-14 w-14 text-detective-accent" />
            </div>
            <h3 className="text-lg font-bold text-detective-800 mb-2">
              Welcome to the MCP Data Detective Agency!
            </h3>
            <CaseFileText />
            
            {/* Example Queries */}
            <div className="w-full max-w-2xl">
              <h4 className="text-sm font-medium text-gray-700 mb-3">Try these examples:</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {exampleQueries.map((query, index) => (
                  <button
                    key={index}
                    onClick={() => setInputValue(query)}
                    className="text-left p-3 text-sm text-detective-600 bg-white border border-gray-200 rounded-lg hover:border-detective-accent hover:bg-detective-50 transition-colors"
                  >
                    {query}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {Array.isArray(messages) && messages.length > 0 ? (
              messages.map((message, index) => (
                <ChatMessage key={message.id || `message-${index}`} message={message} />
              ))
            ) : (
              <div className="text-center text-gray-500 py-8">
                <p>No messages to display</p>
              </div>
            )}
            
            {/* Typing indicator */}
            {isTyping && (
              <div className="flex items-center space-x-2 p-4 bg-white/90 border border-detective-accent/30 rounded-lg shadow-detective">
                <Loader2 className="h-5 w-5 text-detective-accent animate-spin" />
                <span className="text-detective-600">Investigating your request...</span>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="bg-detective-800 border-t border-detective-700 p-3">
        <form onSubmit={handleSubmit} className="flex space-x-2">
          <div className="flex-1">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Describe your investigation or what evidence you're looking for..."
              className="w-full px-4 py-3 border border-detective-600 bg-detective-700 text-white rounded-lg focus:ring-2 focus:ring-detective-accent focus:border-detective-accent resize-none placeholder-gray-400"
              rows="1"
              disabled={isLoading || !isConnected}
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading || !isConnected}
            className="px-6 py-3 bg-detective-accent text-detective-900 rounded-lg hover:bg-detective-accent/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-detective-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </form>
        
        {!isConnected && (
          <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm text-yellow-800">
              ⚠️ Not connected to MCP servers. Please ensure your servers are running.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default ChatInterface; 