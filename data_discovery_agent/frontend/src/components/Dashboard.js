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
        <div className="flex justify-between items-center mb-4 bg-detective-800 p-4 rounded-lg shadow-lg">
          <div className="flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-detective-accent mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="10" cy="10" r="7" />
              <line x1="21" y1="21" x2="15" y2="15" />
            </svg>
            <h1 className="text-2xl font-bold text-white">Evidence Dashboard</h1>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={refreshWidgets}
              className="bg-detective-accent hover:bg-detective-accent/90 text-detective-900 px-3 py-1 rounded text-sm flex items-center shadow-sm"
              disabled={isLoadingWidgets}
            >
              {isLoadingWidgets ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                  <span>Investigating...</span>
                </>
              ) : (
                <span>Refresh Evidence</span>
              )}
            </button>
          </div>
        </div>
        
        {/* Chat Panel Toggle Button */}
        <button
          onClick={toggleChatPanel}
          className="fixed bottom-6 right-6 bg-detective-800 hover:bg-detective-700 text-detective-accent p-3 rounded-full shadow-lg z-10 flex items-center justify-center border-2 border-detective-accent"
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
        <div className="text-center py-12 bg-detective-100 rounded-lg border border-detective-200 shadow-inner">
          <div className="flex flex-col items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-detective-accent mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="10" cy="10" r="7" />
              <line x1="21" y1="21" x2="15" y2="15" />
            </svg>
            <h3 className="text-lg font-bold text-detective-700 mb-2">No Evidence Collected Yet</h3>
            <p className="text-detective-600 max-w-md">Start your investigation by asking the Data Detective to create visualizations of your data.</p>
          </div>
        </div>
      )}
      
      {/* Chat Panel */}
      <div className={`fixed right-0 top-0 h-full bg-white shadow-lg w-96 transition-transform duration-300 transform z-20 ${showChatPanel ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="flex flex-col h-full">
          <div className="p-4 border-b flex justify-between items-center bg-detective-800 text-white">
            <h3 className="font-semibold flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-detective-accent mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="10" cy="10" r="7" />
                <line x1="21" y1="21" x2="15" y2="15" />
              </svg>
              <span>Detective Assistant</span>
            </h3>
            <div className="flex items-center space-x-2">
              <button 
                onClick={clearChat} 
                className="text-detective-900 hover:text-detective-800 text-xs bg-detective-accent px-2 py-1 rounded shadow-sm"
                title="Clear chat history"
              >
                Clear Case
              </button>
              <button onClick={toggleChatPanel} className="text-white hover:text-gray-200">
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
          <div className="p-3 border-t bg-detective-100">
            <p className="text-xs text-detective-600 mb-2 font-medium">Investigation Leads:</p>
            <div className="space-y-2">
              {[
                "Investigate MySQL user distribution with a pie chart",
                "Analyze cache performance patterns over time",
                "Compile evidence of the top database queries",
                "Track suspicious API response time patterns"
              ].map((question, index) => (
                <button
                  key={index}
                  onClick={() => setChatMessage(question)}
                  className="text-xs text-left w-full p-2 bg-white border border-detective-200 rounded hover:bg-detective-50 hover:border-detective-accent transition-colors shadow-sm"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
          
          {/* Chat Input */}
          <div className="p-3 border-t bg-detective-800">
            <form onSubmit={handleChatSubmit} className="flex">
              <input
                type="text"
                value={chatMessage}
                onChange={(e) => setChatMessage(e.target.value)}
                placeholder="Describe what evidence you need..."
                className="flex-grow px-3 py-2 text-sm border border-detective-600 bg-detective-700 text-white rounded-l focus:outline-none focus:ring-1 focus:ring-detective-accent placeholder-gray-400"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading}
                className="bg-detective-accent hover:bg-detective-accent/90 text-detective-900 px-3 py-2 rounded-r disabled:opacity-50 flex items-center justify-center"
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