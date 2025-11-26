import { useState } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Box,
  Button,
  ExpandableSection,
  Alert,
  Badge,
} from '@cloudscape-design/components';
import type { InsightResult } from '../../types/insight';

interface InsightDisplayProps {
  insightResult: InsightResult | null;
  loading?: boolean;
}

export const InsightDisplay: React.FC<InsightDisplayProps> = ({
  insightResult,
  loading = false,
}) => {
  const [copySuccess, setCopySuccess] = useState(false);

  if (loading) {
    return (
      <Container>
        <Box textAlign="center" padding="xxl">
          <SpaceBetween size="m">
            <Box variant="h3">Extracting insights...</Box>
            <Box variant="p" color="text-body-secondary">
              This may take up to 30 seconds
            </Box>
          </SpaceBetween>
        </Box>
      </Container>
    );
  }

  if (!insightResult) {
    return (
      <Container>
        <Box textAlign="center" padding="xxl">
          <SpaceBetween size="m">
            <Box variant="h3">No insights yet</Box>
            <Box variant="p" color="text-body-secondary">
              Select a document and enter a prompt to extract insights
            </Box>
          </SpaceBetween>
        </Box>
      </Container>
    );
  }

  const handleCopyToClipboard = () => {
    const jsonString = JSON.stringify(insightResult.insights, null, 2);
    navigator.clipboard.writeText(jsonString).then(() => {
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    });
  };

  const handleExportJSON = () => {
    const jsonString = JSON.stringify(insightResult.insights, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `insights-${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExportCSV = () => {
    // Flatten the insights object for CSV export
    const flattenObject = (obj: any, prefix = ''): string[][] => {
      const rows: string[][] = [];
      
      for (const [key, value] of Object.entries(obj)) {
        const newKey = prefix ? `${prefix}.${key}` : key;
        
        if (value && typeof value === 'object' && !Array.isArray(value)) {
          rows.push(...flattenObject(value, newKey));
        } else if (Array.isArray(value)) {
          rows.push([newKey, JSON.stringify(value)]);
        } else {
          rows.push([newKey, String(value)]);
        }
      }
      
      return rows;
    };

    const rows = flattenObject(insightResult.insights);
    const csvContent = [
      ['Field', 'Value'],
      ...rows,
    ]
      .map((row) => row.map((cell) => `"${cell}"`).join(','))
      .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `insights-${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const formatTimestamp = (timestamp: number): string => {
    return new Date(timestamp).toLocaleString();
  };

  const renderValue = (value: any): React.ReactNode => {
    if (value === null || value === undefined) {
      return <Box color="text-body-secondary">null</Box>;
    }

    if (typeof value === 'boolean') {
      return <Box>{value ? 'true' : 'false'}</Box>;
    }

    if (typeof value === 'number') {
      return <Box>{value}</Box>;
    }

    if (typeof value === 'string') {
      return <Box>{value}</Box>;
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return <Box color="text-body-secondary">Empty array</Box>;
      }
      
      return (
        <SpaceBetween size="xs">
          {value.map((item, index) => (
            <Box key={index} margin={{ left: 's' }}>
              • {renderValue(item)}
            </Box>
          ))}
        </SpaceBetween>
      );
    }

    if (typeof value === 'object') {
      return (
        <SpaceBetween size="s">
          {Object.entries(value).map(([key, val]) => (
            <Box key={key} margin={{ left: 's' }}>
              <SpaceBetween size="xxs">
                <Box variant="awsui-key-label">{key}</Box>
                {renderValue(val)}
              </SpaceBetween>
            </Box>
          ))}
        </SpaceBetween>
      );
    }

    return <Box>{String(value)}</Box>;
  };

  return (
    <Container
      header={
        <Header
          variant="h2"
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              <Button
                iconName="copy"
                onClick={handleCopyToClipboard}
                disabled={copySuccess}
              >
                {copySuccess ? 'Copied!' : 'Copy'}
              </Button>
              <Button iconName="download" onClick={handleExportJSON}>
                Export JSON
              </Button>
              <Button iconName="download" onClick={handleExportCSV}>
                Export CSV
              </Button>
            </SpaceBetween>
          }
        >
          Extracted Insights
        </Header>
      }
    >
      <SpaceBetween size="l">
        {/* Metadata */}
        <SpaceBetween size="s">
          <Box>
            <SpaceBetween direction="horizontal" size="xs">
              <Badge color={insightResult.source === 'cache' ? 'blue' : 'green'}>
                {insightResult.source === 'cache' ? 'From Cache' : 'Newly Generated'}
              </Badge>
              {insightResult.chunkCount && (
                <Badge>{insightResult.chunkCount} chunks retrieved</Badge>
              )}
            </SpaceBetween>
          </Box>
          <Box variant="small" color="text-body-secondary">
            Generated at: {formatTimestamp(insightResult.timestamp)}
          </Box>
        </SpaceBetween>

        {/* Insights Content */}
        <SpaceBetween size="m">
          {Object.entries(insightResult.insights).map(([key, value]) => (
            <ExpandableSection
              key={key}
              headerText={key}
              variant="container"
              defaultExpanded={true}
            >
              {renderValue(value)}
            </ExpandableSection>
          ))}
        </SpaceBetween>

        {copySuccess && (
          <Alert type="success" dismissible onDismiss={() => setCopySuccess(false)}>
            Insights copied to clipboard
          </Alert>
        )}
      </SpaceBetween>
    </Container>
  );
};
