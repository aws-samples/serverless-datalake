import { useState } from 'react';
import {
  Container,
  SpaceBetween,
  Button,
  Spinner,
  Alert,
} from '@cloudscape-design/components';
import { DocumentSelector } from '../InsightExtraction/DocumentSelector';
import { extractInsights } from '../../services/api';
import type { InsightResponse } from '../../services/api';

// Research prompt template
const RESEARCH_PROMPT = `Generate a comprehensive research report analyzing this entire document. 

Structure your response as a detailed markdown report with the following sections:

# Executive Summary
Provide a high-level overview of the document's main purpose and key findings.

# Key Findings
List and explain the most important discoveries, facts, or conclusions from the document.

# Detailed Analysis
Provide an in-depth analysis of the document's content, organized by major themes or topics.

# Entities and Stakeholders
Identify and describe key people, organizations, locations, and other important entities mentioned.

# Timeline and Events
If applicable, outline significant dates, events, or chronological information.

# Conclusions and Implications
Summarize the broader implications and significance of the document's content.

# Recommendations
If applicable, provide actionable recommendations based on the analysis.

Format your response in clean, well-structured markdown with proper headings, bullet points, and emphasis where appropriate.`;

export const ResearchAgent: React.FC = () => {
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [selectedFileName, setSelectedFileName] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportHtml, setReportHtml] = useState<string>('');

  const handleDocumentSelect = (docId: string, fileName: string) => {
    setSelectedDocId(docId);
    setSelectedFileName(fileName);
    setReportHtml('');
    setError(null);
  };

  const handleGenerateReport = async () => {
    if (!selectedDocId) {
      setError('Please select a document first');
      return;
    }

    setLoading(true);
    setError(null);
    setReportHtml('');

    try {
      const result: InsightResponse = await extractInsights({
        docId: selectedDocId,
        prompt: RESEARCH_PROMPT,
      });

      // Convert the insights to HTML
      const html = convertInsightsToHtml(result);
      setReportHtml(html);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to generate research report';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const convertInsightsToHtml = (result: InsightResponse): string => {
    // Extract the answer which should contain the markdown report
    let markdownContent = result.insights.answer || '';
    
    // If answer is empty, try to construct from other fields
    if (!markdownContent && result.insights.summary) {
      markdownContent = `# Research Report\n\n## Summary\n${result.insights.summary}\n\n`;
      
      if (result.insights.keyPoints && Array.isArray(result.insights.keyPoints)) {
        markdownContent += `## Key Points\n${result.insights.keyPoints.map((p: string) => `- ${p}`).join('\n')}\n\n`;
      }
    }
    
    // Convert markdown to HTML
    let html = markdownContent;
    
    // Escape HTML entities first
    html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Convert code blocks (before other conversions)
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Convert headers (must be at start of line)
    html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // Convert bold and italic (order matters!)
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/_(.+?)_/g, '<em>$1</em>');
    
    // Convert blockquotes
    html = html.replace(/^&gt; (.+)$/gim, '<blockquote>$1</blockquote>');
    
    // Convert horizontal rules
    html = html.replace(/^---$/gim, '<hr>');
    html = html.replace(/^\*\*\*$/gim, '<hr>');
    
    // Split into lines for list processing
    const lines = html.split('\n');
    const processedLines: string[] = [];
    let inUnorderedList = false;
    let inOrderedList = false;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmedLine = line.trim();
      
      // Check for unordered list items
      if (trimmedLine.match(/^[-*+] /)) {
        if (!inUnorderedList) {
          processedLines.push('<ul>');
          inUnorderedList = true;
        }
        processedLines.push(`<li>${trimmedLine.substring(2)}</li>`);
      }
      // Check for ordered list items
      else if (trimmedLine.match(/^\d+\. /)) {
        if (!inOrderedList) {
          processedLines.push('<ol>');
          inOrderedList = true;
        }
        processedLines.push(`<li>${trimmedLine.replace(/^\d+\. /, '')}</li>`);
      }
      // Not a list item
      else {
        if (inUnorderedList) {
          processedLines.push('</ul>');
          inUnorderedList = false;
        }
        if (inOrderedList) {
          processedLines.push('</ol>');
          inOrderedList = false;
        }
        processedLines.push(line);
      }
    }
    
    // Close any open lists
    if (inUnorderedList) processedLines.push('</ul>');
    if (inOrderedList) processedLines.push('</ol>');
    
    html = processedLines.join('\n');
    
    // Convert paragraphs (double line breaks)
    html = html.replace(/\n\n+/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    
    // Wrap in paragraph tags
    html = `<p>${html}</p>`;
    
    // Clean up paragraph tags around block elements
    html = html.replace(/<p><h(\d)>/g, '<h$1>');
    html = html.replace(/<\/h(\d)><\/p>/g, '</h$1>');
    html = html.replace(/<p><ul>/g, '<ul>');
    html = html.replace(/<\/ul><\/p>/g, '</ul>');
    html = html.replace(/<p><ol>/g, '<ol>');
    html = html.replace(/<\/ol><\/p>/g, '</ol>');
    html = html.replace(/<p><pre>/g, '<pre>');
    html = html.replace(/<\/pre><\/p>/g, '</pre>');
    html = html.replace(/<p><blockquote>/g, '<blockquote>');
    html = html.replace(/<\/blockquote><\/p>/g, '</blockquote>');
    html = html.replace(/<p><hr><\/p>/g, '<hr>');
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p><br><\/p>/g, '');
    
    // Unescape HTML entities in code blocks
    html = html.replace(/<code>(.*?)<\/code>/g, (_match: string, content: string) => {
      return `<code>${content.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')}</code>`;
    });
    
    return html;
  };

  const downloadReport = () => {
    if (!reportHtml) return;

    const fullHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Research Report - ${selectedFileName}</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
      line-height: 1.6;
      max-width: 900px;
      margin: 40px auto;
      padding: 20px;
      color: #333;
    }
    h1 { color: #0073bb; border-bottom: 3px solid #0073bb; padding-bottom: 10px; }
    h2 { color: #0073bb; margin-top: 30px; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; }
    h3 { color: #555; margin-top: 20px; }
    h4 { color: #666; margin-top: 15px; }
    ul, ol { margin-left: 20px; }
    li { margin-bottom: 8px; }
    strong { color: #000; }
    code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
    pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }
    .metadata { background: #f9f9f9; padding: 15px; border-left: 4px solid #0073bb; margin-bottom: 30px; }
  </style>
</head>
<body>
  <div class="metadata">
    <strong>Document:</strong> ${selectedFileName}<br>
    <strong>Generated:</strong> ${new Date().toLocaleString()}
  </div>
  ${reportHtml}
</body>
</html>`;

    const blob = new Blob([fullHtml], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `research-report-${selectedDocId}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <SpaceBetween size="l">
      {error && (
        <Alert type="error" dismissible onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <DocumentSelector
        onDocumentSelect={handleDocumentSelect}
        selectedDocId={selectedDocId}
      />

      {selectedDocId && (
        <Container>
          <SpaceBetween size="m">
            <Alert type="info">
              Selected document: <strong>{selectedFileName}</strong>
            </Alert>

            <Button
              variant="primary"
              onClick={handleGenerateReport}
              loading={loading}
              disabled={!selectedDocId || loading}
              iconName="gen-ai"
            >
              Generate Research Report
            </Button>
          </SpaceBetween>
        </Container>
      )}

      {loading && (
        <Container>
          <SpaceBetween size="m" alignItems="center">
            <Spinner size="large" />
            <div style={{ textAlign: 'center' }}>
              Analyzing document and generating comprehensive research report...
              <br />
              <small>This may take a minute for large documents</small>
            </div>
          </SpaceBetween>
        </Container>
      )}

      {reportHtml && !loading && (
        <Container
          header={
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0 }}>Research Report</h2>
              <Button
                iconName="download"
                onClick={downloadReport}
              >
                Download HTML
              </Button>
            </div>
          }
        >
          <div
            className="research-report"
            style={{
              padding: '30px',
              backgroundColor: '#fff',
              borderRadius: '8px',
              lineHeight: '1.8',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", sans-serif',
            }}
          >
            <style>{`
              .research-report h1 {
                color: #0073bb;
                border-bottom: 3px solid #0073bb;
                padding-bottom: 12px;
                margin-top: 0;
                margin-bottom: 24px;
                font-size: 2em;
              }
              .research-report h2 {
                color: #0073bb;
                margin-top: 32px;
                margin-bottom: 16px;
                border-bottom: 2px solid #e0e0e0;
                padding-bottom: 8px;
                font-size: 1.5em;
              }
              .research-report h3 {
                color: #555;
                margin-top: 24px;
                margin-bottom: 12px;
                font-size: 1.25em;
              }
              .research-report h4 {
                color: #666;
                margin-top: 20px;
                margin-bottom: 10px;
                font-size: 1.1em;
              }
              .research-report ul, .research-report ol {
                margin-left: 24px;
                margin-bottom: 16px;
              }
              .research-report li {
                margin-bottom: 8px;
              }
              .research-report p {
                margin-bottom: 16px;
                color: #333;
              }
              .research-report strong {
                color: #000;
                font-weight: 600;
              }
              .research-report em {
                font-style: italic;
                color: #555;
              }
              .research-report code {
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
              }
              .research-report pre {
                background: #f4f4f4;
                padding: 16px;
                border-radius: 6px;
                overflow-x: auto;
                margin-bottom: 16px;
              }
              .research-report blockquote {
                border-left: 4px solid #0073bb;
                padding-left: 16px;
                margin-left: 0;
                color: #555;
                font-style: italic;
              }
            `}</style>
            <div dangerouslySetInnerHTML={{ __html: reportHtml }} />
          </div>
        </Container>
      )}
    </SpaceBetween>
  );
};
