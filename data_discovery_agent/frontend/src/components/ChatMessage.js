import React, { useState, useEffect } from 'react';
import { Bot, User, Loader2, CheckCircle, XCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
import DataTable from './DataTable';
import ChartWidget from './ChartWidget';
import StreamingIndicator from './StreamingIndicator';
import ThinkingProcess from './ThinkingProcess';
import PlanConfirmationDialog from './PlanConfirmationDialog';
import HTMLContentRenderer from './HTMLContentRenderer';
import { useChat } from '../contexts/ChatContext';
import axios from 'axios';
import SherlockAvatar from './SherlockAvatar';

// Dashboard renderer component
function DashboardRenderer({ filename, metadata }) {
  const [htmlContent, setHtmlContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await axios.get(`/api/dashboard/${filename}`);
        setHtmlContent(response.data);
      } catch (err) {
        setError('Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    };

    if (filename) {
      fetchDashboard();
    }
  }, [filename]);

  if (loading) {
    return (
      <div className="mt-4 flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="ml-2">Loading dashboard...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-4 text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
        {error}
      </div>
    );
  }

  return (
    <div className="mt-4">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
          <span className="text-sm font-medium text-blue-700">Generated Dashboard</span>
        </div>
        {metadata && (
          <p className="text-xs text-blue-600 mt-1">
            Generated at: {new Date(metadata.generated_at).toLocaleString()}
          </p>
        )}
      </div>
      <iframe
        srcDoc={htmlContent}
        title="Dashboard Preview"
        className="border border-gray-200 rounded-lg overflow-hidden w-full"
        style={{ height: '600px' }}
        sandbox="allow-scripts"
      />
    </div>
  );
}

// Utility function to sanitize markdown content
const sanitizeMarkdown = (content) => {
  if (!content || typeof content !== 'string') {
    return '';
  }
  
  try {
    // Remove any null bytes or other problematic characters
    let sanitized = content.replace(/\0/g, '');
    
    // Ensure proper line endings
    sanitized = sanitized.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    
    // Remove any excessive whitespace that might cause parsing issues
    sanitized = sanitized.replace(/\n{4,}/g, '\n\n\n');
    
    // Fix malformed table structures that can cause parsing errors
    sanitized = sanitized.replace(/\|(?:\s*\|)+/g, (match) => {
      // Ensure table rows have proper cell separators
      return match.replace(/\|\s*\|/g, '| |');
    });
    
    // Fix incomplete table rows
    const lines = sanitized.split('\n');
    const fixedLines = lines.map(line => {
      // If line starts with | but doesn't end with |, add it
      if (line.trim().startsWith('|') && !line.trim().endsWith('|') && line.includes('|')) {
        return line.trim() + ' |';
      }
      return line;
    });
    
    sanitized = fixedLines.join('\n');
    
    // Remove any remaining problematic characters that could break parsing
    sanitized = sanitized.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
    
    return sanitized;
  } catch (error) {
    console.warn('Error sanitizing markdown:', error);
    // Return the original content if sanitization fails
    return content;
  }
};

// Safe ReactMarkdown wrapper with error boundary
class SafeReactMarkdown extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ReactMarkdown error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="font-medium">Error rendering markdown:</p>
          <p className="text-sm">{this.state.error?.message || 'Unknown error'}</p>
          <div className="mt-2 p-2 bg-gray-100 rounded text-sm font-mono whitespace-pre-wrap">
            {this.props.children}
          </div>
        </div>
      );
    }

    try {
      const remarkPlugins = [];
      // Only add remarkGfm if it's available and compatible
      try {
        if (remarkGfm) {
          remarkPlugins.push(remarkGfm);
        }
      } catch (pluginError) {
        console.warn('remarkGfm plugin error, continuing without it:', pluginError);
      }

      return (
        <ReactMarkdown
          remarkPlugins={remarkPlugins}
          components={{
            // Enhanced code block rendering
            code({ node, inline, className, children, ...props }) {
              try {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <SyntaxHighlighter
                    style={tomorrow}
                    language={match[1]}
                    PreTag="div"
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code className={`${className} bg-gray-100 px-1 py-0.5 rounded text-sm font-mono`} {...props}>
                    {children}
                  </code>
                );
              } catch (codeError) {
                console.warn('Code rendering error:', codeError);
                return (
                  <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono" {...props}>
                    {children}
                  </code>
                );
              }
            },
            // Enhanced paragraph rendering
            p({ children, ...props }) {
              return (
                <p className="mb-3 leading-relaxed" {...props}>
                  {children}
                </p>
              );
            },
            // Enhanced list rendering
            ul({ children, ...props }) {
              return (
                <ul className="list-disc list-inside mb-3 space-y-1 ml-4" {...props}>
                  {children}
                </ul>
              );
            },
            ol({ children, ...props }) {
              return (
                <ol className="list-decimal list-inside mb-3 space-y-1 ml-4" {...props}>
                  {children}
                </ol>
              );
            },
            // Enhanced list item rendering
            li({ children, ...props }) {
              return (
                <li className="leading-relaxed" {...props}>
                  {children}
                </li>
              );
            },
            // Enhanced heading rendering
            h1({ children, ...props }) {
              return (
                <h1 className="text-xl font-bold mb-3 mt-4 text-gray-900" {...props}>
                  {children}
                </h1>
              );
            },
            h2({ children, ...props }) {
              return (
                <h2 className="text-lg font-semibold mb-2 mt-3 text-gray-900" {...props}>
                  {children}
                </h2>
              );
            },
            h3({ children, ...props }) {
              return (
                <h3 className="text-base font-medium mb-2 mt-2 text-gray-900" {...props}>
                  {children}
                </h3>
              );
            },
            // Enhanced blockquote rendering
            blockquote({ children, ...props }) {
              return (
                <blockquote className="border-l-4 border-gray-300 pl-4 italic text-gray-600 mb-3" {...props}>
                  {children}
                </blockquote>
              );
            },
            // Enhanced table rendering
            table({ children, ...props }) {
              return (
                <div className="overflow-x-auto mb-3">
                  <table className="min-w-full border border-gray-300" {...props}>
                    {children}
                  </table>
                </div>
              );
            },
            th({ children, ...props }) {
              return (
                <th className="border border-gray-300 px-3 py-2 bg-gray-50 font-medium text-left" {...props}>
                  {children}
                </th>
              );
            },
            td({ children, ...props }) {
              return (
                <td className="border border-gray-300 px-3 py-2" {...props}>
                  {children}
                </td>
              );
            },
          }}
        >
          {this.props.children}
        </ReactMarkdown>
      );
    } catch (error) {
      console.error('Error in ReactMarkdown render:', error);
      return (
        <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="font-medium">Error rendering markdown:</p>
          <p className="text-sm">{error?.message || 'Unknown error'}</p>
          <div className="mt-2 p-2 bg-gray-100 rounded text-sm font-mono">
            {this.props.children}
          </div>
        </div>
      );
    }
  }
}

function ChatMessage({ message }) {
  // Get the confirmPlan and rejectPlan functions from context
  const { confirmPlan, rejectPlan } = useChat();
  
  // Validate message object
  if (!message || typeof message !== 'object') {
    return (
      <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
        <p className="font-medium">Error: Invalid message object</p>
      </div>
    );
  }

  const isUser = message.type === 'user';
  const isLoading = message.isLoading;
  
  const handleConfirmPlan = () => {
    if (message.plan && message.originalQuery) {
      confirmPlan(message.plan, message.originalQuery);
    }
  };
  
  const handleRejectPlan = () => {
    if (message.plan && message.originalQuery) {
      rejectPlan(message.plan, message.originalQuery);
    }
    
  };

  const formatTimestamp = (timestamp) => {
    try {
      if (!timestamp) return 'Unknown time';
      return new Date(timestamp).toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    } catch (error) {
      console.error('Error formatting timestamp:', error);
      return 'Invalid time';
    }
  };

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="space-y-3">
          {/* Tool usage indicator */}
          {message.toolUse && (
            <div className="bg-detective-accent/10 border border-detective-accent/30 rounded-lg p-3">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-detective-accent rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-detective-700">
                  Using tool: {message.toolUse.tool}
                </span>
              </div>
              {message.toolUse.description && (
                <p className="text-xs text-detective-600 mt-1">
                  {message.toolUse.description}
                </p>
              )}
            </div>
          )}
          
          {/* Real-time thinking indicator */}
          {message.thinking && (
            <div className="bg-detective-accent/10 border border-detective-accent/30 rounded-lg p-3">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-detective-accent rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-detective-700">Investigating...</span>
              </div>
              <div className="text-sm text-detective-600 mt-2 italic max-h-32 overflow-y-auto">
                <p className="whitespace-pre-wrap leading-relaxed">
                  {message.thinking}
                </p>
              </div>
            </div>
          )}
          
          {/* Default loading indicator */}
          {!message.thinking && !message.toolUse && (
            <div className="flex items-center space-x-2">
              <Loader2 className="h-4 w-4 animate-spin text-detective-accent" />
              <span className="text-detective-600">Investigating...</span>
            </div>
          )}
          
          <StreamingIndicator />
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
        {message.toolUse && !isLoading && (
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
        {message.thinkingSteps && message.thinkingSteps.length > 0 && !isLoading && (
          <ThinkingProcess thinkingSteps={message.thinkingSteps} />
        )}
        
        {/* Simple thinking content history */}
        {message.thinking && !isLoading && (
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
        {message.needsConfirmation && message.plan && (
          <PlanConfirmationDialog 
            plan={message.plan} 
            onConfirm={handleConfirmPlan} 
            onReject={handleRejectPlan} 
          />
        )}
        
        {/* Markdown content */}
        {(!message.needsConfirmation || message.content) && (
          <div className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-ul:text-gray-700 prose-ol:text-gray-700 prose-li:text-gray-700 prose-strong:text-gray-900 prose-em:text-gray-700">
            {message.content && typeof message.content === 'string' ? (
              <SafeReactMarkdown>
                {sanitizeMarkdown(message.content)}
              </SafeReactMarkdown>
            ) : message.content ? (
              <div className="text-gray-600 whitespace-pre-wrap">
                {String(message.content)}
              </div>
            ) : !message.needsConfirmation && (
              <div className="text-gray-400 italic">
                No content available
              </div>
            )}
          </div>
        )}

        {/* Data table if present */}
        {message.data && (
          <div className="mt-4">
            <DataTable data={message.data} />
          </div>
        )}

        {/* Charts if present */}
        {message.charts && message.charts.length > 0 && (
          <div className="mt-4 space-y-4">
            {message.charts.map((chart, index) => (
              <ChartWidget key={index} chartData={chart} />
            ))}
          </div>
        )}

        {/* Dashboard if present */}
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
            {message.dashboard.startsWith('<!DOCTYPE html>') || message.dashboard.startsWith('<html') ? (
              <HTMLContentRenderer 
                htmlContent={message.dashboard} 
                metadata={message.dashboardMetadata} 
                title="Generated Dashboard"
              />
            ) : (
              <div 
                className="border border-gray-200 rounded-lg overflow-hidden"
                dangerouslySetInnerHTML={{ __html: message.dashboard }}
              />
            )}
          </div>
        )}

        {/* Dashboard file if present */}
        {message.dashboardFile && (
          <DashboardRenderer filename={message.dashboardFile} metadata={message.dashboardMetadata} />
        )}
        
        {/* HTML content from custom_summarization_agent */}
        {message.htmlContent && (
          <HTMLContentRenderer 
            htmlContent={message.htmlContent} 
            metadata={message.metadata} 
            title={message.htmlContentTitle || "Analysis Report"}
          />
        )}
      </div>
    );
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex max-w-4xl ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div className={`flex-shrink-0 ${isUser ? 'ml-3' : 'mr-3'}`}>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
            isUser 
              ? 'bg-detective-700 text-white' 
              : 'bg-detective-accent/20 text-detective-accent'
          }`}>
            {isUser ? (
              <User className="h-4 w-4" />
            ) : (
              <SherlockAvatar className="h-5 w-5" />
            )}
          </div>
        </div>

        {/* Message content */}
        <div className={`flex-1 ${isUser ? 'text-right' : 'text-left'}`}>
          <div className={`inline-block p-4 rounded-lg ${
            isUser 
              ? 'bg-detective-700 text-white shadow-detective' 
              : 'bg-white/90 border border-detective-200 shadow-detective'
          }`}>
            {renderContent()}
          </div>
          
          {/* Timestamp */}
          <div className={`mt-2 text-xs text-gray-500 ${isUser ? 'text-right' : 'text-left'}`}>
            {formatTimestamp(message.timestamp)}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatMessage; 