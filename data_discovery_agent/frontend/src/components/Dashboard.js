import React, { useEffect, useState, useRef } from 'react';
import { tabSessionManager } from '../utils/TabSessionManager';
import { toast } from 'react-hot-toast';
import { Send, Bot, X, MessageSquare, Loader2 } from 'lucide-react';
import { useChat } from '../contexts/ChatContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
import PlanConfirmationDialog from './PlanConfirmationDialog';
import axios from 'axios';
// Dashboard/Widget renderer component
function WidgetRenderer({ filename, metadata, inGrid = false }) {
  const [htmlContent, setHtmlContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchContent = async () => {
      try {
        // Use the appropriate API endpoint based on content type
        const response = await fetch(`/api/widget/${filename}`);
        if (!response.ok) throw new Error(`Failed to fetch widget: ${response.status}`);
        const data = await response.text();
        setHtmlContent(data);
      } catch (err) {
        setError(`Failed to load widget: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    if (filename) {
      fetchContent();
    }
  }, [filename]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="ml-2 text-sm">Loading widget...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg p-2 text-sm">
        {error}
      </div>
    );
  }

  // For widgets in the grid, use a more compact display
  if (inGrid) {
    return (
      <iframe
        srcDoc={htmlContent}
        title="Widget"
        className="w-full h-full border-0 rounded"
        style={{ minHeight: '100%', width: '100%', overflow: 'visible' }}
        sandbox="allow-scripts allow-same-origin"
        scrolling="yes"
        onLoad={(e) => {
          try {
            // Attempt to adjust iframe height based on content
            const iframe = e.target;
            if (iframe.contentWindow && iframe.contentDocument) {
              const height = iframe.contentDocument.body.scrollHeight;
              iframe.style.height = `${height + 20}px`;
            }
          } catch (err) {
            console.error('Error adjusting iframe height:', err);
          }
        }}
      />
    );
  }

  // For widgets in chat messages, use the full display with header
  return (
    <div className="mt-4">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
          <span className="text-sm font-medium text-blue-700">Generated Widget</span>
        </div>
        {metadata && (
          <p className="text-xs text-blue-600 mt-1">
            Generated at: {new Date(metadata.generated_at).toLocaleString()}
          </p>
        )}
      </div>
      <iframe
        srcDoc={htmlContent}
        title="Widget Preview"
        className="border border-gray-200 rounded-lg overflow-hidden w-full"
        style={{ height: '500px' }}
        sandbox="allow-scripts allow-same-origin"
        scrolling="yes"
        onLoad={(e) => {
          try {
            // Attempt to adjust iframe height based on content
            const iframe = e.target;
            if (iframe.contentWindow && iframe.contentDocument) {
              const height = iframe.contentDocument.body.scrollHeight;
              iframe.style.height = `${height + 20}px`;
            }
          } catch (err) {
            console.error('Error adjusting iframe height:', err);
          }
        }}
      />
    </div>
  );
}



const Dashboard = () => {
  const [widgets, setWidgets] = useState([]);
  const [chatMessage, setChatMessage] = useState('');
  const [widgetPreview, setWidgetPreview] = useState(null);
  const [showChatPanel, setShowChatPanel] = useState(false);
  const [isLoadingWidgets, setIsLoadingWidgets] = useState(false);
  const chatEndRef = useRef(null);
  
  // Use the shared chat context
  const { 
    messages: chatMessages, 
    isLoading, 
    sendMessage, 
    socketRef,
    confirmPlan,
    rejectPlan,
    clearMessages
  } = useChat();

  // Fetch all widgets on component mount
  useEffect(() => {
    const fetchWidgets = async () => {
      setIsLoadingWidgets(true);
      try {
        const response = await fetch('/api/widget/history');
        if (!response.ok) throw new Error('Failed to fetch widgets');
        
        const data = await response.json();
        console.log('Widget history response:', data);
        if (data.widgets && Array.isArray(data.widgets)) {
          // Transform the API response into widget objects
          const widgetObjects = data.widgets.map(widget => ({
            id: widget.filename,
            path: `/api/widget/${widget.filename}`,
            title: widget.filename.replace('.html', ''),
            created_at: widget.created_at,
            metadata: {"generated_at": widget.created_at}
          }));
          setWidgets(widgetObjects);
        } else if (data.dashboards && Array.isArray(data.dashboards)) {
          // Fallback for backward compatibility
          const widgetObjects = data.dashboards.map(widget => ({
            id: widget.filename,
            path: `/api/widget/${widget.filename}`,
            title: widget.filename.replace('.html', ''),
            created_at: widget.created_at,
            metadata: {"generated_at": widget.created_at}
          }));
          setWidgets(widgetObjects);
        }
      } catch (error) {
        console.error('Error fetching widgets:', error);
        toast.error('Failed to load widgets');
      } finally {
        setIsLoadingWidgets(false);
      }
    };
    
    fetchWidgets();
  }, []);

  useEffect(() => {
    // Set up socket event listeners for widget-specific events
    if (socketRef && socketRef.current) {
      // Listen for widget updates (progress)
      socketRef.current.on('widget_update', (data) => {
        console.log('Widget update:', data);
        if (data.status === 'processing') {
          toast(data.message);
        }
        
        // Add thinking updates to the last message
        if (data.type === 'thinking') {
          console.log('Thinking update received:', data);
        }
      });
      
      // Listen for widget responses (completed widgets)
      socketRef.current.on('widget_response', (data) => {
        console.log('Widget response:', data);
        if (data.status === 'success') {
          // Show preview instead of immediately adding to dashboard
          setWidgetPreview({
            id: Date.now(),
            path: data.widget_path,
            type: data.widget_type,
            title: data.widget_title || 'New Widget'
          });
        } else if (data.status === 'error') {
          toast.error(data.message);
        }
      });
    }
    
    return () => {
      if (socketRef && socketRef.current) {
        socketRef.current.off('widget_update');
        socketRef.current.off('widget_response');
      }
    };
  }, [socketRef]);

  const handleCreateWidget = (type) => {
    if (socketRef && socketRef.current && socketRef.current.connected) {
      socketRef.current.emit('build_widget', { type });
    } else {
      toast.error('Not connected to server');
    }
  };
  
  const toggleChatPanel = () => {
    setShowChatPanel(!showChatPanel);
  };
  
  useEffect(() => {
    // Scroll to bottom of chat when messages change
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);
  
  const handleChatSubmit = (e) => {
    e.preventDefault();
    if (!chatMessage.trim() || isLoading) return;
    
    // Use the sendMessage function from ChatContext
    sendMessage(chatMessage);
    setChatMessage('');
    
    // Toggle the chat panel open if it's closed
    if (!showChatPanel) {
      setShowChatPanel(true);
    }
    
    // Log the current messages to debug
    console.log('Current messages after sending:', chatMessages);
  };
  
  const handleConfirmPlan = (plan, originalQuery) => {
    confirmPlan(plan, originalQuery, true);
  };
  
  const handleRejectPlan = (plan, originalQuery) => {
    rejectPlan(plan, originalQuery);
  };
  
  const handleAddWidget = () => {
    if (widgetPreview) {
      setWidgets(prevWidgets => [...prevWidgets, widgetPreview]);
      toast.success('Widget added to dashboard!');
      setWidgetPreview(null);
    }
  };
  
  // Refresh widgets from the API
  const refreshWidgets = async () => {
    setIsLoadingWidgets(true);
    try {
      const response = await fetch('/api/widget/history');
      if (!response.ok) throw new Error('Failed to fetch widgets');
      
      const data = await response.json();
      console.log('Refresh widgets response:', data);
      if (data.widgets && Array.isArray(data.widgets)) {
        const widgetObjects = data.widgets.map(widget => ({
          id: widget.filename,
          path: `/api/widget/${widget.filename}`,
          title: widget.filename.replace('.html', ''),
          created_at: widget.created_at,
          metadata: {"generated_at": widget.created_at}
        }));
        setWidgets(widgetObjects);
      } else if (data.dashboards && Array.isArray(data.dashboards)) {
        // Fallback for backward compatibility
        const widgetObjects = data.dashboards.map(widget => ({
          id: widget.filename,
          path: `/api/widget/${widget.filename}`,
          title: widget.filename.replace('.html', ''),
          created_at: widget.created_at,
          metadata: {"generated_at": widget.created_at}
        }));
        setWidgets(widgetObjects);
      }
    } catch (error) {
      console.error('Error refreshing widgets:', error);
      toast.error('Failed to refresh widgets');
    } finally {
      setIsLoadingWidgets(false);
    }
  };
  
  
  const clearChat = () => {
    clearMessages();
    toast.success('Chat session cleared');
    // Reset socket connection
    if (socketRef && socketRef.current) {
      // Disconnect and reconnect to reset the session
      socketRef.current.disconnect();
      socketRef.current.connect();
    }
  };
  
  // Function to render message content similar to ChatMessage.js
  const renderContent = (message) => {
    if (message.isLoading) {
      return (
        <div className="space-y-3">
          {/* Tool usage indicator */}
          {message.toolUse && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-blue-700">
                  Using tool: {message.toolUse.tool}
                </span>
              </div>
              {message.toolUse.description && (
                <p className="text-xs text-blue-600 mt-1">
                  {message.toolUse.description}
                </p>
              )}
            </div>
          )}
          
          {/* Real-time thinking indicator */}
          {message.thinking && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-blue-700">Thinking...</span>
              </div>
              <div className="text-sm text-blue-600 mt-2 italic max-h-32 overflow-y-auto">
                <p className="whitespace-pre-wrap leading-relaxed">
                  {message.thinking}
                </p>
              </div>
            </div>
          )}
          
          {/* Default loading indicator */}
          {!message.thinking && !message.toolUse && (
            <div className="flex items-center space-x-2">
              <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
              <span className="text-sm text-gray-500">Processing...</span>
            </div>
          )}
        </div>
      );
    }

    if (message.error) {
      return (
        <div className="text-red-600">
          <p className="font-medium">Error:</p>
          <p>{message.content}</p>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        {/* Tool usage history */}
        {message.toolUse && !message.isLoading && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
              <span className="text-sm font-medium text-blue-700">
                Used tool: {message.toolUse.tool}
              </span>
            </div>
            {message.toolUse.description && (
              <p className="text-xs text-blue-600 mt-1">
                {message.toolUse.description}
              </p>
            )}
          </div>
        )}
        
        {/* Thinking process history */}
        {message.thinkingSteps && message.thinkingSteps.length > 0 && !message.isLoading && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-4">
            <div className="flex items-center space-x-2 mb-2">
              <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
              <span className="text-sm font-medium text-gray-700">Thinking Process</span>
            </div>
            <div className="text-sm text-gray-600">
              <ol className="list-decimal list-inside space-y-1">
                {message.thinkingSteps.map((step, idx) => (
                  <li key={idx} className="whitespace-pre-wrap leading-relaxed">{step}</li>
                ))}
              </ol>
            </div>
          </div>
        )}
        
        {/* Simple thinking content history */}
        {message.thinking && !message.isLoading && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-4">
            <div className="flex items-center space-x-2 mb-2">
              <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
              <span className="text-sm font-medium text-gray-700">Thinking Process</span>
            </div>
            <div className="text-sm text-gray-600 italic whitespace-pre-wrap leading-relaxed">
              {message.thinking}
            </div>
          </div>
        )}
        
        {/* Plan Confirmation Dialog */}
        {(message.needsConfirmation || message.plan) && (
          <PlanConfirmationDialog 
            plan={message.plan || (message.needsConfirmation ? message.needsConfirmation.plan : null)} 
            onConfirm={() => handleConfirmPlan(
              message.plan || (message.needsConfirmation ? message.needsConfirmation.plan : null), 
              message.originalQuery || (message.needsConfirmation ? message.needsConfirmation.original_query : '')
            )} 
            onReject={() => handleRejectPlan(
              message.plan || (message.needsConfirmation ? message.needsConfirmation.plan : null), 
              message.originalQuery || (message.needsConfirmation ? message.needsConfirmation.original_query : '')
            )} 
          />
        )}
        
        {/* Regular content */}
        {message.content && (
          <div className="whitespace-pre-wrap">{message.content}</div>
        )}

        {/* Widget/Dashboard file if present */}
        {(message.widgetFile) && (
          <WidgetRenderer 
            filename={message.widgetFile} 
            metadata={message.widgetMetadata}
          />
        )}

        {/* Dashboard HTML content if present */}
        {message.dashboard && (
          <div className="mt-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                <span className="text-sm font-medium text-blue-700">Generated Dashboard</span>
              </div>
              {message.dashboardMetadata && (
                <p className="text-xs text-blue-600 mt-1">
                  Generated at: {new Date(message.dashboardMetadata.generated_at).toLocaleString()}
                </p>
              )}
            </div>
            <div 
              className="border border-gray-200 rounded-lg overflow-hidden"
              dangerouslySetInnerHTML={{ __html: message.dashboard }}
            />
          </div>
        )}
      </div>
    );
  };

  // Function to render a single message
  const renderMessage = (message) => {
    if (!message) return null;
    return (
      <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
        <div className={`max-w-[90%] p-3 rounded-lg ${message.type === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-100'}`}>
          {renderContent(message)}
        </div>
      </div>
    );
  };

  const removeWidget = (widgetId) => {
    setWidgets(widgets.filter(widget => widget.id !== widgetId));
  };

  return (
    <div className="p-4 relative">
      <div className="mb-6">
        <div className="flex justify-between items-center mb-4 bg-white p-6 rounded-xl shadow-sm border border-detective-200">
          <div className="flex items-center">
            <div className="h-10 w-10 bg-detective-accent rounded-xl flex items-center justify-center mr-3">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 12l2 2 4-4"/>
                <path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"/>
                <path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"/>
                <path d="M12 3c0 1-1 3-3 3s-3-2-3-3 1-3 3-3 3 2 3 3"/>
                <path d="M12 21c0-1-1-3-3-3s-3 2-3 3 1 3 3 3 3-2 3-3"/>
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-detective-900">Analytics Dashboard</h1>
              <p className="text-sm text-detective-600 mt-1">Interactive data visualizations and insights</p>
            </div>
          </div>
          <div className="flex space-x-3">
            <button
              onClick={refreshWidgets}
              className="modern-button-secondary flex items-center"
              disabled={isLoadingWidgets}
            >
              {isLoadingWidgets ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span>Refreshing...</span>
                </>
              ) : (
                <span>Refresh Widgets</span>
              )}
            </button>
          </div>
        </div>
        
        {/* Chat Panel Toggle Button */}
        <button
          onClick={toggleChatPanel}
          className="fixed bottom-6 right-6 bg-detective-accent hover:bg-detective-accent/90 text-white p-4 rounded-full shadow-lg z-10 flex items-center justify-center"
        >
          {showChatPanel ? <X size={20} /> : <MessageSquare size={20} />}
        </button>
      </div>
      
      {isLoading && (
        <div className="flex justify-center my-8">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      )}
      
      {/* 4x4 Grid Layout for Widgets */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-10">
        {widgets.map(widget => (
          <div key={widget.id} className="bg-white rounded-lg shadow-md overflow-hidden">
            <div className="flex justify-between items-center p-3 border-b">
              <h3 className="font-semibold text-sm truncate">{widget.title}</h3>
              <button 
                onClick={() => removeWidget(widget.id)}
                className="text-red-500 hover:text-red-700"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
            <div className="p-2 h-[600px] overflow-auto" style={{ minHeight: '600px' }}>
              <WidgetRenderer 
                filename={widget.id} 
                metadata={widget.metadata}
                inGrid={true}
              />
            </div>
          </div>
        ))}
      </div>
      
      {/* Loading state */}
      {isLoadingWidgets && (
        <div className="flex justify-center my-8">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      )}
      
      {/* Empty state */}
      {widgets.length === 0 && !isLoadingWidgets && !isLoading && (
        <div className="text-center py-16 bg-white rounded-xl border border-detective-200 shadow-sm">
          <div className="flex flex-col items-center">
            <div className="h-16 w-16 bg-detective-accent/10 rounded-2xl flex items-center justify-center mb-6">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-detective-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 12l2 2 4-4"/>
                <path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"/>
                <path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"/>
                <path d="M12 3c0 1-1 3-3 3s-3-2-3-3 1-3 3-3 3 2 3 3"/>
                <path d="M12 21c0-1-1-3-3-3s-3 2-3 3 1 3 3 3 3-2 3-3"/>
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-detective-900 mb-2">No Widgets Yet</h3>
            <p className="text-detective-600 max-w-md">Start creating interactive visualizations by asking the assistant to analyze your data.</p>
          </div>
        </div>
      )}
      
      {/* Chat Panel */}
      <div className={`fixed right-0 top-0 h-full bg-white shadow-xl w-96 transition-transform duration-300 transform z-20 border-l border-detective-200 ${showChatPanel ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="flex flex-col h-full">
          <div className="p-4 border-b border-detective-200 flex justify-between items-center bg-white">
            <h3 className="font-semibold flex items-center text-detective-900">
              <div className="h-6 w-6 bg-detective-accent rounded-lg flex items-center justify-center mr-2">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 12l2 2 4-4"/>
                  <path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"/>
                  <path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"/>
                  <path d="M12 3c0 1-1 3-3 3s-3-2-3-3 1-3 3-3 3 2 3 3"/>
                  <path d="M12 21c0-1-1-3-3-3s-3 2-3 3 1 3 3 3 3-2 3-3"/>
                </svg>
              </div>
              <span>Analytics Assistant</span>
            </h3>
            <div className="flex items-center space-x-2">
              <button 
                onClick={clearChat} 
                className="modern-button-secondary text-xs px-3 py-1"
                title="Clear chat history"
              >
                Clear Chat
              </button>
              <button onClick={toggleChatPanel} className="text-detective-500 hover:text-detective-700 p-1">
                <X size={18} />
              </button>
            </div>
          </div>
          
          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {Array.isArray(chatMessages) && chatMessages.length > 0 ? (
              chatMessages.map(message => renderMessage(message))
            ) : (
              <div className="text-center py-8">
                <p className="text-gray-500">Hi there! I can help you create widgets using natural language. What kind of widget would you like to create?</p>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          
          {/* Sample Questions */}
          <div className="p-4 border-t border-detective-200 bg-detective-50">
            <p className="text-xs text-detective-600 mb-3 font-medium">Quick Actions:</p>
            <div className="space-y-2">
              {[
                "Create a user distribution pie chart from MySQL",
                "Analyze performance patterns over time",
                "Show top database queries by frequency",
                "Track API response time trends"
              ].map((question, index) => (
                <button
                  key={index}
                  onClick={() => setChatMessage(question)}
                  className="text-xs text-left w-full p-3 bg-white border border-detective-200 rounded-lg hover:bg-detective-50 hover:border-detective-accent transition-all duration-200 shadow-sm"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
          
          {/* Chat Input */}
          <div className="p-4 border-t border-detective-200 bg-white">
            <form onSubmit={handleChatSubmit} className="flex space-x-2">
              <input
                type="text"
                value={chatMessage}
                onChange={(e) => setChatMessage(e.target.value)}
                placeholder="Ask me to create a visualization..."
                className="flex-grow px-3 py-2 text-sm border border-detective-300 bg-white text-detective-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-detective-accent focus:border-detective-accent placeholder-detective-500"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading}
                className="modern-button px-3 py-2 disabled:opacity-50 flex items-center justify-center"
              >
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send size={16} />}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;