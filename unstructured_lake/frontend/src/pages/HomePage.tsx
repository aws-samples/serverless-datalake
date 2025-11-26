import { useState } from 'react';
import {
  ContentLayout,
  Header,
  SpaceBetween,
  Container,
} from '@cloudscape-design/components';
import { Layout } from '../components/Common/Layout';
import { UploadButton } from '../components/DocumentUpload/UploadButton';
import { DocumentList } from '../components/DocumentUpload/DocumentList';

export const HomePage: React.FC = () => {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleUploadComplete = () => {
    // Refresh the document list
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <Layout>
      <ContentLayout
        header={
          <Header
            variant="h1"
            description="Upload PDF documents and extract structured insights using AI"
          >
            Document Insight Extraction
          </Header>
        }
      >
        <SpaceBetween size="l">
          <Container
            header={
              <Header variant="h2" description="Upload a PDF document to get started">
                Upload Document
              </Header>
            }
          >
            <UploadButton onUploadComplete={handleUploadComplete} />
          </Container>

          <DocumentList refreshTrigger={refreshTrigger} />
        </SpaceBetween>
      </ContentLayout>
    </Layout>
  );
};
