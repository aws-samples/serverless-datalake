export interface Insight {
  summary?: string;
  keyPoints?: string[];
  entities?: Entity[];
  metadata?: InsightMetadata;
  [key: string]: any;
}

export interface Entity {
  name: string;
  type: string;
  context: string;
}

export interface InsightMetadata {
  confidence?: number;
  processingTime?: number;
}

export interface InsightResult {
  insights: Insight;
  source: 'cache' | 'generated';
  chunkCount?: number;
  timestamp: number;
}

export interface CachedInsight {
  docId: string;
  extractionTimestamp: number;
  prompt: string;
  insights: Insight;
  modelId: string;
  expiresAt: number;
}
