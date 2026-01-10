import React, { useState, useRef, useEffect } from 'react';
import { useChat } from '../contexts/ChatContext';
import { Send, Trash2, Loader2 } from 'lucide-react';
import ChatMessage from './ChatMessage';

function ChatInterface() {
  const { 
    messages, 
    isLoading, 
    isConnected,
    sendMessage, 
    clearMessages,
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

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };
  
  const handleClearChat = () => {
    // Clear messages in the state
    clearMessages();
  };

  const exampleQueries = [
    "Investigate all tables in the Athena",
    "Give me the schema of the iceberg_employees table in apache_iceberg database on Athena",
    "Get me a count of employees in the iceberg_employees table",
    "Summarize the Amazon 10K filing report",
    "Give me key insights on Spinosaurus",
    "List my vector buckets and indexes",
    "How many records are in the products table? I need evidence.",
    "Give me all data points on serverless-rag-demo repo under aws-samples org on Github",
    "Create a detailed report of the MySQL database structure",
    "What are the top 10 products by sales? Look for anomalies.",
    "Analyze the connection between users and their purchase history"
  ];

  return (
    <div className="flex flex-col h-full bg-detective-50">
      {/* Header */}
      <div className="modern-header px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className="mr-4">
              <div className="h-12 w-12 bg-detective-accent rounded-xl flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 12l2 2 4-4"/>
                  <path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"/>
                  <path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"/>
                  <path d="M12 3c0 1-1 3-3 3s-3-2-3-3 1-3 3-3 3 2 3 3"/>
                  <path d="M12 21c0-1-1-3-3-3s-3 2-3 3 1 3 3 3 3-2 3-3"/>
                </svg>
              </div>
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-detective-900">DataDiscovery Agent</h1>
              <p className="text-sm text-detective-600 mt-1">
                Intelligent data analytics and insights platform
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <button
              onClick={handleClearChat}
              className="modern-button-secondary flex items-center"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Clear Chat
            </button>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 bg-detective-50">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-20 h-20 bg-detective-accent/10 rounded-2xl flex items-center justify-center mb-6">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-detective-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 12l2 2 4-4"/>
                <path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"/>
                <path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"/>
                <path d="M12 3c0 1-1 3-3 3s-3-2-3-3 1-3 3-3 3 2 3 3"/>
                <path d="M12 21c0-1-1-3-3-3s-3 2-3 3 1 3 3 3 3-2 3-3"/>
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-detective-900 mb-2">
              Welcome to DataDiscovery Agent
            </h3>
            <p className="text-detective-600 mb-8 max-w-md">
              Your intelligent data analytics companion. Ask questions about your data sources and get comprehensive insights.
            </p>
            
            {/* Example Queries */}
            <div className="w-full max-w-4xl">
              <h4 className="text-sm font-medium text-detective-700 mb-4">Try these examples:</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {exampleQueries.map((query, index) => (
                  <button
                    key={index}
                    onClick={() => setInputValue(query)}
                    className="text-left p-4 text-sm text-detective-700 bg-white border border-detective-200 rounded-xl hover:border-detective-accent hover:bg-detective-50 transition-all duration-200 shadow-sm hover:shadow-md"
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
              <div className="text-center text-detective-500 py-8">
                <p>No messages to display</p>
              </div>
            )}
            
            {/* Typing indicator */}
            {isTyping && (
              <div className="flex items-center space-x-3 p-4 bg-white border border-detective-200 rounded-2xl shadow-sm">
                <Loader2 className="h-5 w-5 text-detective-accent animate-spin" />
                <span className="text-detective-600">Analyzing your request...</span>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="bg-white border-t border-detective-200 p-4">
        <form onSubmit={handleSubmit} className="flex space-x-3">
          <div className="flex-1">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything about your data..."
              className="w-full px-4 py-3 border border-detective-300 bg-white text-detective-900 rounded-xl focus:ring-2 focus:ring-detective-accent focus:border-detective-accent resize-none placeholder-detective-500"
              rows="1"
              disabled={isLoading || !isConnected}
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading || !isConnected}
            className="modern-button px-6 py-3 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed"
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