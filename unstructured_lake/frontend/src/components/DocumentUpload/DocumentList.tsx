import { useEffect, useState } from 'react';
import {
  Table,
  Box,
  SpaceBetween,
  Button,
  StatusIndicator,
  Header,
} from '@cloudscape-design/components';
import { listDocuments } from '../../services/api';
import type { Document } from '../../services/api';

interface DocumentListProps {
  refreshTrigger?: number;
  onDocumentSelect?: (document: Document) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  refreshTrigger,
  onDocumentSelect,
}) => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedItems, setSelectedItems] = useState<Document[]>([]);

  const fetchDocuments = async () => {
    setLoading(true);

    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [refreshTrigger]);

  // Auto-refresh processing documents every 5 seconds
  useEffect(() => {
    const hasProcessingDocs = documents.some(doc => 
      doc.status === 'processing' || doc.status === 'in-progress'
    );

    if (hasProcessingDocs) {
      const interval = setInterval(() => {
        fetchDocuments();
      }, 15000); // Refresh every 5 seconds

      return () => clearInterval(interval);
    }
  }, [documents]);

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const getStatusIndicator = (document: Document) => {
    const errorCount = document.errorCount || 0;
    const totalChunks = document.totalChunks || 0;
    
    switch (document.status) {
      case 'processing':
      case 'in-progress':
        const processingText = document.currentPage && document.pageCount
          ? `Processing (${document.currentPage}/${document.pageCount} pages)`
          : 'Processing';
        return <StatusIndicator type="in-progress">{processingText}</StatusIndicator>;
      case 'completed':
        const statusText = errorCount > 0 
          ? `Completed (${errorCount} error${errorCount > 1 ? 's' : ''}, ${totalChunks} chunks)`
          : `Completed (${totalChunks} chunks)`;
        return (
          <StatusIndicator type={errorCount > 0 ? "warning" : "success"}>
            {statusText}
          </StatusIndicator>
        );
      case 'failed':
        return <StatusIndicator type="error">Failed</StatusIndicator>;
      default:
        return <StatusIndicator type="pending">Unknown</StatusIndicator>;
    }
  };

  return (
    <Table
      columnDefinitions={[
        {
          id: 'fileName',
          header: 'File Name',
          cell: (item) => item.fileName,
          sortingField: 'fileName',
        },
        {
          id: 'uploadDate',
          header: 'Upload Date',
          cell: (item) => formatDate(item.uploadDate),
          sortingField: 'uploadDate',
        },
        {
          id: 'fileSize',
          header: 'Size',
          cell: (item) => formatFileSize(item.fileSize),
          sortingField: 'fileSize',
        },
        {
          id: 'status',
          header: 'Status',
          cell: (item) => getStatusIndicator(item),
          sortingField: 'status',
        },
        {
          id: 'pageCount',
          header: 'Total Pages',
          cell: (item) => item.pageCount || '-',
          sortingField: 'pageCount',
        },
        {
          id: 'currentPage',
          header: 'Current Page',
          cell: (item) => {
            if (item.status === 'processing' || item.status === 'in-progress') {
              return item.currentPage !== undefined ? item.currentPage : '-';
            }
            return '-';
          },
          sortingField: 'currentPage',
        },
        {
          id: 'totalChunks',
          header: 'Chunks',
          cell: (item) => item.totalChunks || '-',
          sortingField: 'totalChunks',
        },
      ]}
      items={documents}
      loading={loading}
      loadingText="Loading documents..."
      selectionType="single"
      selectedItems={selectedItems}
      onSelectionChange={({ detail }) => {
        setSelectedItems(detail.selectedItems);
        if (detail.selectedItems.length > 0) {
          onDocumentSelect?.(detail.selectedItems[0]);
        }
      }}
      empty={
        <Box textAlign="center" color="inherit">
          <SpaceBetween size="m">
            <b>No documents</b>
            <Box variant="p" color="inherit">
              Upload a document to get started
            </Box>
          </SpaceBetween>
        </Box>
      }
      header={
        <Header
          actions={
            <Button
              iconName="refresh"
              onClick={fetchDocuments}
              loading={loading}
            >
              Refresh
            </Button>
          }
        >
          Documents
        </Header>
      }
    />
  );
};
