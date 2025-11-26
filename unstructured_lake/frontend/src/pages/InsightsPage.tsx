import { useState } from 'react';
import {
  ContentLayout,
  Header,
  SpaceBetween,
  Alert,
  Tabs,
} from '@cloudscape-design/components';
import { Layout } from '../components/Common/Layout';
import { DocumentSelector } from '../components/InsightExtraction/DocumentSelector';
import { PromptInput } from '../components/InsightExtraction/PromptInput';
import { InsightDisplay } from '../components/InsightExtraction/InsightDisplay';
import { ResearchAgent } from '../components/ResearchAgent/ResearchAgent';
import { extractInsights } from '../services/api';
import type { InsightResult } from '../types/insight';

export const InsightsPage: React.FC = () => {
  const [activeTabId, setActiveTabId] = useState('insights');
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [selectedFileName, setSelectedFileName] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [insightResult, setInsightResult] = useState<InsightResult | null>(null);

  const handleDocumentSelect = (docId: string, fileName: string) => {
    setSelectedDocId(docId);
    setSelectedFileName(fileName);
    setInsightResult(null);
    setError(null);
  };

  const handlePromptSubmit = async (prompt: string) => {
    if (!selectedDocId) {
      setError('Please select a document first');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await extractInsights({
        docId: selectedDocId,
        prompt,
      });

      setInsightResult(result);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to extract insights';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <ContentLayout
        header={
          <Header
            variant="h1"
            description="Extract structured insights or generate comprehensive research reports from your documents"
          >
            Document Analysis
          </Header>
        }
      >
        <Tabs
          activeTabId={activeTabId}
          onChange={({ detail }) => setActiveTabId(detail.activeTabId)}
          tabs={[
            {
              id: 'insights',
              label: 'Extract Insights',
              content: (
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
                    <>
                      <Alert type="info">
                        Selected document: <strong>{selectedFileName}</strong>
                      </Alert>

                      <PromptInput
                        onSubmit={handlePromptSubmit}
                        loading={loading}
                        disabled={!selectedDocId}
                      />
                    </>
                  )}

                  <InsightDisplay insightResult={insightResult} loading={loading} />
                </SpaceBetween>
              ),
            },
            {
              id: 'research',
              label: 'Research Agent',
              content: <ResearchAgent />,
            },
          ]}
        />
      </ContentLayout>
    </Layout>
  );
};
