import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';

/**
 * Component to render HTML content from the custom_summarization_agent
 * 
 * @param {string} htmlContent - The HTML content to render
 * @param {object} metadata - Optional metadata about the content
 * @param {boolean} fullHeight - Whether to render at full height or fixed height
 * @param {string} title - Optional title for the content
 */
function HTMLContentRenderer({ htmlContent, metadata, fullHeight = false, title = 'Analysis Report' }) {
  const [loading, setLoading] = useState(!htmlContent);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (htmlContent) {
      setLoading(false);
    }
  }, [htmlContent]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="ml-2">Loading content...</span>
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
      {title && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
            <span className="text-sm font-medium text-blue-700">{title}</span>
          </div>
          {metadata && metadata.generated_at && (
            <p className="text-xs text-blue-600 mt-1">
              Generated at: {new Date(metadata.generated_at).toLocaleString()}
            </p>
          )}
        </div>
      )}
      <iframe
        srcDoc={htmlContent}
        title={title || "HTML Content"}
        className="border border-gray-200 rounded-lg overflow-hidden w-full"
        style={{ height: fullHeight ? '100%' : '600px', minHeight: '400px' }}
        sandbox="allow-scripts"
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

export default HTMLContentRenderer;