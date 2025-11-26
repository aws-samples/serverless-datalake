import axios from 'axios';
import type { AxiosInstance, AxiosError } from 'axios';
import { getIdToken } from './auth';
import { loadConfig } from '../config/config';

let apiClient: AxiosInstance | null = null;

// Initialize API client with configuration
const initializeApiClient = async (): Promise<AxiosInstance> => {
  if (apiClient) {
    return apiClient;
  }

  const config = await loadConfig();

  // Create axios instance
  apiClient = axios.create({
    baseURL: config.apiUrl,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request interceptor to add authentication token
  apiClient.interceptors.request.use(
    async (config) => {
      try {
        const token = await getIdToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch (error) {
        console.error('Failed to get auth token:', error);
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor for error handling
  apiClient.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      if (error.response?.status === 401) {
        // Unauthorized - redirect to login
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }
  );

  return apiClient;
};

// Get API client instance
const getApiClient = async (): Promise<AxiosInstance> => {
  if (!apiClient) {
    return await initializeApiClient();
  }
  return apiClient;
};



// Types
export interface PresignedUrlRequest {
  fileName: string;
  fileSize: number;
  contentType: string;
  connectionId?: string; // Optional WebSocket connection ID for progress notifications
}

export interface PresignedUrlResponse {
  url: string;
  fields: {
    key: string;
    [key: string]: string;
  };
  docId: string;
  expiresIn: number;
}

export interface Document {
  docId: string;
  fileName: string;
  uploadDate: string;
  pageCount?: number;
  status: 'processing' | 'completed' | 'failed' | 'in-progress';
  fileSize: number;
  currentPage?: number;
  totalChunks?: number;
  errorCount?: number;
}

export interface ProcessingStatus {
  docId: string;
  status: 'in-progress' | 'completed' | 'failed';
  totalPages?: number;
  currentPage?: number;
  filename?: string;
  startTime?: number;
  lastUpdated?: number;
  completedAt?: number;
  failedAt?: number;
  errorMessage?: string;
  errorCount:number;
  totalChunks?: number;
  progressMessage?: string;
}

export interface InsightRequest {
  docId: string;
  prompt: string;
}

export interface InsightResponse {
  insights: {
    summary?: string;
    keyPoints?: string[];
    entities?: Array<{
      name: string;
      type: string;
      context: string;
    }>;
    metadata?: {
      confidence?: number;
      processingTime?: number;
    };
    [key: string]: any;
  };
  source: 'cache' | 'generated';
  chunkCount?: number;
  timestamp: number;
}

export interface CachedInsight {
  docId: string;
  extractionTimestamp: number;
  prompt: string;
  insights: any;
  modelId: string;
  expiresAt: number;
}

export interface ImageInsightsRequest {
  image: string; // Base64 encoded image
  prompt?: string; // Optional user prompt
}

export interface ImageInsightsResponse {
  is_valid_image: boolean;
  validation_message: string;
  key_insights: {
    name?: string;
    age?: string;
    document_type?: string;
    other_details?: string[];
  };
  forgery_detection: {
    suspicious: boolean;
    confidence: number;
    indicators: string[];
  };
  qr_code_detected: boolean;
  qr_bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  qr_code_data?: string;
  qr_code_image?: string; // Base64 encoded cropped QR code image
  raw_response?: string;
}

// API Functions

/**
 * Get a presigned POST URL for uploading a document to S3
 */
export const getPresignedUrl = async (
  request: PresignedUrlRequest
): Promise<PresignedUrlResponse> => {
  const client = await getApiClient();
  const response = await client.post<PresignedUrlResponse>(
    '/documents/presigned-url',
    request
  );
  return response.data;
};

/**
 * Upload a file directly to S3 using presigned POST URL
 */
export const uploadToS3 = async (
  presignedUrl: PresignedUrlResponse,
  file: File
): Promise<void> => {
  const formData = new FormData();
  
  // Add all fields from presigned URL
  Object.entries(presignedUrl.fields).forEach(([key, value]) => {
    formData.append(key, value);
  });
  
  // Add the file last
  formData.append('file', file);

  // Upload to S3 (no auth headers needed for presigned URL)
  await axios.post(presignedUrl.url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

/**
 * List all documents for the current user
 */
export const listDocuments = async (): Promise<Document[]> => {
  const client = await getApiClient();
  const response = await client.get<Document[]>('/documents');
  return response.data;
};

/**
 * Extract insights from a document using a natural language prompt
 */
export const extractInsights = async (
  request: InsightRequest
): Promise<InsightResponse> => {
  const client = await getApiClient();
  const response = await client.post<InsightResponse>(
    '/insights/extract',
    request
  );
  return response.data;
};

/**
 * Get cached insights for a specific document
 */
export const getInsights = async (docId: string): Promise<CachedInsight[]> => {
  const client = await getApiClient();
  const response = await client.get<CachedInsight[]>(`/insights/${docId}`);
  return response.data;
};

/**
 * Get processing status for a document
 */
export const getProcessingStatus = async (docId: string): Promise<ProcessingStatus> => {
  const client = await getApiClient();
  const response = await client.get<ProcessingStatus>(`/documents/${docId}/status`);
  return response.data;
};

/**
 * Delete a document
 */
export const deleteDocument = async (docId: string): Promise<void> => {
  const client = await getApiClient();
  await client.delete(`/documents/${docId}`);
};

/**
 * Analyze an image using Claude vision model
 */
export const analyzeImage = async (
  request: ImageInsightsRequest
): Promise<ImageInsightsResponse> => {
  const client = await getApiClient();
  const response = await client.post<ImageInsightsResponse>(
    '/image-insights/analyze',
    request
  );
  return response.data;
};

export default getApiClient;
