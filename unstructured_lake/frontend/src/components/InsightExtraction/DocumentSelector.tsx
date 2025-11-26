import { useEffect, useState } from 'react';
import {
  Select,
  FormField,
  SpaceBetween,
  Button,
} from '@cloudscape-design/components';
import type { SelectProps } from '@cloudscape-design/components';
import { listDocuments } from '../../services/api';
import type { Document } from '../../services/api';

interface DocumentSelectorProps {
  onDocumentSelect: (docId: string, fileName: string) => void;
  selectedDocId?: string;
}

export const DocumentSelector: React.FC<DocumentSelectorProps> = ({
  onDocumentSelect,
  selectedDocId,
}) => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedOption, setSelectedOption] = useState<SelectProps.Option | null>(null);

  const fetchDocuments = async () => {
    setLoading(true);

    try {
      const docs = await listDocuments();
      
      // Filter to only show completed documents
      const completedDocs = docs.filter((doc) => doc.status === 'completed');
      setDocuments(completedDocs);

      // If a document was previously selected, restore the selection
      if (selectedDocId) {
        const selectedDoc = completedDocs.find((doc) => doc.docId === selectedDocId);
        if (selectedDoc) {
          setSelectedOption({
            label: selectedDoc.fileName,
            value: selectedDoc.docId,
          });
        }
      }
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleSelectionChange = (option: SelectProps.Option | null) => {
    setSelectedOption(option);
    if (option) {
      onDocumentSelect(option.value || '', option.label || '');
    }
  };

  const options: SelectProps.Option[] = documents.map((doc) => ({
    label: doc.fileName,
    value: doc.docId,
    description: `${doc.pageCount || 0} pages - Uploaded ${new Date(doc.uploadDate).toLocaleDateString()}`,
  }));

  return (
    <SpaceBetween size="xs">
      <FormField
        label="Select Document"
        description="Choose a completed document to extract insights from"
      >
        <SpaceBetween size="xs" direction="horizontal">
          <Select
            selectedOption={selectedOption}
            onChange={({ detail }) => handleSelectionChange(detail.selectedOption)}
            options={options}
            placeholder="Choose a document"
            empty="No completed documents available"
            loadingText="Loading documents..."
            statusType={loading ? 'loading' : 'finished'}
            filteringType="auto"
          />
          <Button
            iconName="refresh"
            onClick={fetchDocuments}
            loading={loading}
            ariaLabel="Refresh documents"
          />
        </SpaceBetween>
      </FormField>
    </SpaceBetween>
  );
};
