import fetch from 'node-fetch';
import { EmbeddingService } from './embeddings';

/**
 * Google Gemini embedding service implementation
 * Supports task-specific optimization and variable dimensions
 */
export class GeminiEmbeddingService implements EmbeddingService {
  private apiKey: string;
  private model: string;
  private dimensions: number;
  private taskType: GeminiTaskType;

  constructor(
    apiKey: string, 
    model: string = 'gemini-embedding-001',
    dimensions: number = 768, // Can be 768, 1536, or 3072
    taskType: GeminiTaskType = GeminiTaskType.RETRIEVAL_QUERY
  ) {
    this.apiKey = apiKey;
    this.model = model;
    this.dimensions = dimensions;
    this.taskType = taskType;
  }

  async generateEmbedding(text: string): Promise<number[]> {
    try {
      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:embedContent?key=${this.apiKey}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            model: `models/${this.model}`,
            content: {
              parts: [{ text }]
            },
            taskType: this.taskType,
            outputDimensionality: this.dimensions
          }),
        }
      );

      if (!response.ok) {
        const errorBody = await response.text();
        console.error('Gemini API error details:', errorBody);
        throw new Error(`Gemini API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json() as any;
      const embedding = data.embedding.values;

      // Normalize embeddings for dimensions other than 3072
      if (this.dimensions !== 3072) {
        return this.normalizeEmbedding(embedding);
      }

      return embedding;
    } catch (error) {
      throw new Error(`Failed to generate Gemini embedding: ${error}`);
    }
  }

  /**
   * Normalize embedding vector
   */
  private normalizeEmbedding(embedding: number[]): number[] {
    const magnitude = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    return embedding.map(val => val / magnitude);
  }

  getDimensions(): number {
    return this.dimensions;
  }

  getModelName(): string {
    return `gemini/${this.model}`;
  }
}

/**
 * Gemini task types for optimized embeddings
 */
export enum GeminiTaskType {
  SEMANTIC_SIMILARITY = 'SEMANTIC_SIMILARITY',
  CLASSIFICATION = 'CLASSIFICATION',
  CLUSTERING = 'CLUSTERING',
  RETRIEVAL_DOCUMENT = 'RETRIEVAL_DOCUMENT',
  RETRIEVAL_QUERY = 'RETRIEVAL_QUERY',
  CODE_RETRIEVAL_QUERY = 'CODE_RETRIEVAL_QUERY',
  QUESTION_ANSWERING = 'QUESTION_ANSWERING',
  FACT_VERIFICATION = 'FACT_VERIFICATION'
}

/**
 * Gemini vs Voyage comparison utility
 */
export class EmbeddingComparison {
  /**
   * Compare Gemini and Voyage for different use cases
   */
  static getComparison() {
    return {
      gemini: {
        model: 'gemini-embedding-001',
        dimensions: [768, 1536, 3072],
        taskTypes: Object.values(GeminiTaskType),
        advantages: [
          'Task-specific optimization',
          'Variable dimensions (MRL technique)',
          'Normalized embeddings at 3072',
          'Google infrastructure and reliability',
          'Integrated with Google ecosystem'
        ],
        limitations: [
          'No published accuracy benchmarks vs Voyage',
          'Token limits not clearly documented',
          'Potentially higher cost at scale',
          'Requires Google Cloud account'
        ],
        bestFor: [
          'Applications already using Google Cloud',
          'Need for task-specific optimization',
          'Variable dimension requirements',
          'Question-answering systems'
        ]
      },
      voyage: {
        model: 'voyage-3.5-lite',
        dimensions: 1024,
        accuracy: '66.1%',
        tokenLimit: 32000,
        advantages: [
          'Proven high accuracy (66.1% vs OpenAI 39.2%)',
          'Large token limit (32k)',
          'Cost-effective ($0.02/M tokens)',
          '200M free tokens',
          'Optimized for retrieval tasks'
        ],
        limitations: [
          'Fixed dimensions (1024)',
          'No task-specific optimization',
          'Single model variant for lite tier',
          'Less ecosystem integration'
        ],
        bestFor: [
          'Long document processing',
          'Cost-sensitive applications',
          'General-purpose retrieval',
          'High accuracy requirements'
        ]
      }
    };
  }

  /**
   * Estimate costs for project
   */
  static estimateCosts(totalTokens: number) {
    return {
      voyage: {
        freeTokens: 200_000_000,
        costPerMillion: 0.02,
        estimatedCost: Math.max(0, (totalTokens - 200_000_000) / 1_000_000 * 0.02)
      },
      gemini: {
        // Gemini pricing varies by region and usage
        note: 'Gemini pricing varies by region. Check Google Cloud pricing for your region.',
        approximateCostPerMillion: 0.025, // Approximate
        estimatedCost: totalTokens / 1_000_000 * 0.025
      }
    };
  }
}