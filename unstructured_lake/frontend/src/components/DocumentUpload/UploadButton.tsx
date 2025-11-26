import { useState } from 'react';
import { FileUpload, Button, SpaceBetween, Alert } from '@cloudscape-design/components';
import { getPresignedUrl, uploadToS3 } from '../../services/api';
import { websocketService } from '../../services/websocket';
import { UploadProgress } from './UploadProgress';

interface UploadButtonProps {
  onUploadComplete?: (docId: string) => void;
  onUploadError?: (error: string) => void;
}

export const UploadButton: React.FC<UploadButtonProps> = ({
  onUploadComplete,
  onUploadError,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadingDocId, setUploadingDocId] = useState<string | null>(null);

  /**
   * Sanitize filename to remove whitespaces and special characters
   * Keep only alphanumeric characters, hyphens, underscores, and dots
   */
  const sanitizeFilename = (filename: string): string => {
    // Split filename into name and extension
    const lastDotIndex = filename.lastIndexOf('.');
    const name = lastDotIndex > 0 ? filename.substring(0, lastDotIndex) : filename;
    const extension = lastDotIndex > 0 ? filename.substring(lastDotIndex) : '';

    // Replace whitespaces with underscores and remove special characters
    const sanitizedName = name
      .replace(/\s+/g, '_') // Replace whitespaces with underscores
      .replace(/[^a-zA-Z0-9_-]/g, ''); // Remove special characters, keep alphanumeric, underscore, hyphen

    // Sanitize extension (keep only alphanumeric)
    const sanitizedExtension = extension.replace(/[^a-zA-Z0-9.]/g, '');

    return sanitizedName + sanitizedExtension;
  };

  const handleFileChange = (files: File[]) => {
    if (files.length > 0) {
      const file = files[0];
      
      // Validate file type
      if (file.type !== 'application/pdf') {
        setError('Please select a PDF file');
        return;
      }

      // Validate file size (100 MB limit)
      const maxSize = 100 * 1024 * 1024; // 100 MB
      if (file.size > maxSize) {
        setError('File size must be less than 100 MB');
        return;
      }

      setSelectedFile(file);
      setError(null);
    } else {
      setSelectedFile(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      // Connect to WebSocket for progress updates
      await websocketService.connect();

      // Get presigned URL with connection ID for progress notifications
      const connectionId = websocketService.getConnectionId();
      const sanitizedFileName = sanitizeFilename(selectedFile.name);
      const presignedUrlResponse = await getPresignedUrl({
        fileName: sanitizedFileName,
        fileSize: selectedFile.size,
        contentType: selectedFile.type,
        connectionId: connectionId || undefined, // Include connection ID if available
      });

      setUploadingDocId(presignedUrlResponse.docId);

      // Upload file to S3
      await uploadToS3(presignedUrlResponse, selectedFile);

      // File uploaded successfully, WebSocket will handle progress updates
      console.log('File uploaded successfully, docId:', presignedUrlResponse.docId);
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
      setUploadingDocId(null);
      onUploadError?.(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  const handleUploadComplete = (docId: string) => {
    setUploadingDocId(null);
    setSelectedFile(null);
    onUploadComplete?.(docId);
  };

  const handleUploadError = (errorMessage: string) => {
    setError(errorMessage);
    setUploadingDocId(null);
    onUploadError?.(errorMessage);
  };

  return (
    <SpaceBetween size="m">
      {error && (
        <Alert type="error" dismissible onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {uploadingDocId ? (
        <UploadProgress
          docId={uploadingDocId}
          fileName={selectedFile?.name || ''}
          onComplete={handleUploadComplete}
          onError={handleUploadError}
        />
      ) : (
        <>
          <FileUpload
            onChange={({ detail }) => handleFileChange(detail.value)}
            value={selectedFile ? [selectedFile] : []}
            i18nStrings={{
              uploadButtonText: (e) => (e ? 'Choose files' : 'Choose file'),
              dropzoneText: (e) => (e ? 'Drop files to upload' : 'Drop file to upload'),
              removeFileAriaLabel: (e) => `Remove file ${e + 1}`,
              limitShowFewer: 'Show fewer files',
              limitShowMore: 'Show more files',
              errorIconAriaLabel: 'Error',
            }}
            showFileLastModified
            showFileSize
            showFileThumbnail
            tokenLimit={1}
            constraintText="PDF files only, maximum 100 MB"
          />

          <Button
            variant="primary"
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            loading={uploading}
          >
            {uploading ? 'Uploading...' : 'Upload Document'}
          </Button>
        </>
      )}
    </SpaceBetween>
  );
};
