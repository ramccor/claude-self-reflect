import { spawn } from 'child_process';
import fetch from 'node-fetch';

export interface EmbeddingService {
  generateEmbedding(text: string): Promise<number[]>;
  getDimensions(): number;
  getModelName(): string;
}

/**
 * OpenAI embedding service - primary choice for production
 */
export class OpenAIEmbeddingService implements EmbeddingService {
  private apiKey: string;
  private model: string;
  private dimensions: number;

  constructor(apiKey: string, model: string = 'text-embedding-3-small') {
    this.apiKey = apiKey;
    this.model = model;
    this.dimensions = model === 'text-embedding-3-small' ? 1536 : 3072;
  }

  async generateEmbedding(text: string): Promise<number[]> {
    try {
      const response = await fetch('https://api.openai.com/v1/embeddings', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input: text,
          model: this.model,
        }),
      });

      if (!response.ok) {
        const errorBody = await response.text();
        console.error('OpenAI API error details:', errorBody);
        throw new Error(`OpenAI API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json() as any;
      return data.data[0].embedding;
    } catch (error) {
      throw new Error(`Failed to generate OpenAI embedding: ${error}`);
    }
  }

  getDimensions(): number {
    return this.dimensions;
  }

  getModelName(): string {
    return `openai/${this.model}`;
  }
}

/**
 * Voyage AI embedding service - high accuracy option
 */
export class VoyageEmbeddingService implements EmbeddingService {
  private apiKey: string;
  private model: string;
  private dimensions: number;

  constructor(apiKey: string, model: string = 'voyage-3.5-lite') {
    this.apiKey = apiKey;
    this.model = model;
    this.dimensions = 1024; // Voyage default dimensions
  }

  async generateEmbedding(text: string): Promise<number[]> {
    try {
      const response = await fetch('https://api.voyageai.com/v1/embeddings', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input: [text],
          model: this.model,
          input_type: 'query', // Use query type for search
        }),
      });

      if (!response.ok) {
        const errorBody = await response.text();
        console.error('Voyage API error details:', errorBody);
        throw new Error(`Voyage API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json() as any;
      return data.data[0].embedding;
    } catch (error) {
      throw new Error(`Failed to generate Voyage embedding: ${error}`);
    }
  }

  getDimensions(): number {
    return this.dimensions;
  }

  getModelName(): string {
    return `voyage/${this.model}`;
  }
}

/**
 * Local sentence-transformers embedding service - fallback option
 */
export class LocalEmbeddingService implements EmbeddingService {
  private pythonScript: string;
  private modelName: string;
  private dimensions: number;

  constructor(modelName: string = 'sentence-transformers/all-MiniLM-L6-v2') {
    this.modelName = modelName;
    this.dimensions = 384; // all-MiniLM-L6-v2 dimensions
    
    this.pythonScript = `
import sys
import json
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('${modelName}')
text = sys.stdin.read()
embedding = model.encode(text).tolist()
print(json.dumps(embedding))
`;
  }

  async generateEmbedding(text: string): Promise<number[]> {
    return new Promise((resolve, reject) => {
      const python = spawn('python3', ['-c', this.pythonScript]);
      
      let output = '';
      let error = '';

      python.stdout.on('data', (data) => {
        output += data.toString();
      });

      python.stderr.on('data', (data) => {
        error += data.toString();
      });

      python.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Python process exited with code ${code}: ${error}`));
          return;
        }

        try {
          const embedding = JSON.parse(output.trim());
          resolve(embedding);
        } catch (e) {
          reject(new Error(`Failed to parse embedding: ${e}`));
        }
      });

      python.stdin.write(text);
      python.stdin.end();
    });
  }

  getDimensions(): number {
    return this.dimensions;
  }

  getModelName(): string {
    return this.modelName;
  }
}

/**
 * Mock embedding service for development/testing
 */
export class MockEmbeddingService implements EmbeddingService {
  private dimensions: number = 384;

  async generateEmbedding(text: string): Promise<number[]> {
    // Generate a deterministic fake embedding based on text
    const embedding = new Array(this.dimensions).fill(0);
    for (let i = 0; i < Math.min(text.length, this.dimensions); i++) {
      embedding[i] = (text.charCodeAt(i) % 256) / 256;
    }
    return embedding;
  }

  getDimensions(): number {
    return this.dimensions;
  }

  getModelName(): string {
    return 'mock/deterministic';
  }
}

/**
 * Factory to create appropriate embedding service with fallback chain
 */
export async function createEmbeddingService(config?: {
  openaiApiKey?: string;
  voyageApiKey?: string;
  preferLocal?: boolean;
  modelName?: string;
}): Promise<EmbeddingService> {
  // 1. Try Voyage AI if API key is provided (highest accuracy)
  if (config?.voyageApiKey && !config.preferLocal) {
    try {
      console.error(`Attempting to create Voyage AI service with key: ${config.voyageApiKey.substring(0, 10)}...`);
      const service = new VoyageEmbeddingService(config.voyageApiKey, config.modelName);
      // Test the API key with a simple request
      await service.generateEmbedding('test');
      console.error('Using Voyage AI embedding service');
      return service;
    } catch (error) {
      console.error('Voyage AI embedding service failed, falling back to OpenAI:', error);
    }
  }

  // 2. Try OpenAI if API key is provided and not preferring local
  if (config?.openaiApiKey && !config.preferLocal) {
    try {
      const service = new OpenAIEmbeddingService(config.openaiApiKey, config.modelName);
      // Test the API key with a simple request
      await service.generateEmbedding('test');
      console.error('Using OpenAI embedding service');
      return service;
    } catch (error) {
      console.error('OpenAI embedding service failed, falling back to local:', error);
    }
  }

  // 2. Try local sentence-transformers
  try {
    const checkScript = `
import sentence_transformers
print("OK")
`;
    
    const python = spawn('python3', ['-c', checkScript]);
    
    const hasLocalModel = await new Promise<boolean>((resolve) => {
      python.on('close', (code) => {
        resolve(code === 0);
      });
    });

    if (hasLocalModel) {
      console.error('Using local sentence-transformers embedding service');
      return new LocalEmbeddingService(config?.modelName);
    }
  } catch (error) {
    console.error('Local embedding service check failed:', error);
  }

  // 3. Fall back to mock embeddings
  console.error('Warning: No embedding service available, using mock embeddings');
  console.error('For production use, provide OPENAI_API_KEY or install sentence-transformers');
  return new MockEmbeddingService();
}

/**
 * Configuration helper to detect which embedding model was used for existing data
 */
export async function detectEmbeddingModel(qdrantUrl: string, collectionName: string): Promise<{
  model: string;
  dimensions: number;
}> {
  try {
    const response = await fetch(`${qdrantUrl}/collections/${collectionName}`);
    const data = await response.json() as any;
    
    const dimensions = data.result?.config?.params?.vectors?.size || 384;
    
    // Infer model from dimensions
    if (dimensions === 1024) {
      return { model: 'voyage-3.5-lite', dimensions };
    } else if (dimensions === 1536) {
      return { model: 'text-embedding-3-small', dimensions };
    } else if (dimensions === 3072) {
      return { model: 'text-embedding-3-large', dimensions };
    } else if (dimensions === 384) {
      return { model: 'sentence-transformers/all-MiniLM-L6-v2', dimensions };
    }
    
    return { model: 'unknown', dimensions };
  } catch (error) {
    console.error('Failed to detect embedding model:', error);
    return { model: 'sentence-transformers/all-MiniLM-L6-v2', dimensions: 384 };
  }
}