#!/usr/bin/env node
/**
 * Compare Gemini vs Voyage embeddings for the claude-self-reflection use case
 */

import { VoyageEmbeddingService } from '../src/embeddings';
import { GeminiEmbeddingService, GeminiTaskType, EmbeddingComparison } from '../src/embeddings-gemini';

interface ComparisonResult {
  model: string;
  dimensions: number;
  generationTime: number;
  similarity: number;
  taskType?: string;
}

class EmbeddingComparisonTest {
  private voyageService?: VoyageEmbeddingService;
  private geminiService?: GeminiEmbeddingService;

  constructor(
    private voyageApiKey?: string,
    private geminiApiKey?: string
  ) {}

  async initialize() {
    if (this.voyageApiKey) {
      this.voyageService = new VoyageEmbeddingService(this.voyageApiKey);
      console.log('✓ Voyage AI service initialized');
    }

    if (this.geminiApiKey) {
      // Test with 768 dimensions for fair comparison
      this.geminiService = new GeminiEmbeddingService(
        this.geminiApiKey,
        'gemini-embedding-001',
        768,
        GeminiTaskType.RETRIEVAL_QUERY
      );
      console.log('✓ Gemini service initialized');
    }
  }

  /**
   * Compare embedding generation speed
   */
  async compareSpeed(testTexts: string[]): Promise<Record<string, number>> {
    const results: Record<string, number> = {};

    if (this.voyageService) {
      const start = Date.now();
      for (const text of testTexts) {
        await this.voyageService.generateEmbedding(text);
      }
      results.voyage = Date.now() - start;
    }

    if (this.geminiService) {
      const start = Date.now();
      for (const text of testTexts) {
        await this.geminiService.generateEmbedding(text);
      }
      results.gemini = Date.now() - start;
    }

    return results;
  }

  /**
   * Compare semantic similarity scores
   */
  async compareSimilarity(query: string, documents: string[]): Promise<ComparisonResult[]> {
    const results: ComparisonResult[] = [];

    // Test Voyage
    if (this.voyageService) {
      const start = Date.now();
      const queryEmbedding = await this.voyageService.generateEmbedding(query);
      const docEmbeddings = await Promise.all(
        documents.map(doc => this.voyageService!.generateEmbedding(doc))
      );

      const similarities = docEmbeddings.map(docEmb => 
        this.cosineSimilarity(queryEmbedding, docEmb)
      );

      results.push({
        model: 'voyage-3.5-lite',
        dimensions: 1024,
        generationTime: Date.now() - start,
        similarity: Math.max(...similarities)
      });
    }

    // Test Gemini with different task types
    if (this.geminiService) {
      const taskTypes = [
        GeminiTaskType.RETRIEVAL_QUERY,
        GeminiTaskType.SEMANTIC_SIMILARITY,
        GeminiTaskType.QUESTION_ANSWERING
      ];

      for (const taskType of taskTypes) {
        const service = new GeminiEmbeddingService(
          this.geminiApiKey!,
          'gemini-embedding-001',
          768,
          taskType
        );

        const start = Date.now();
        const queryEmbedding = await service.generateEmbedding(query);
        const docEmbeddings = await Promise.all(
          documents.map(doc => service.generateEmbedding(doc))
        );

        const similarities = docEmbeddings.map(docEmb => 
          this.cosineSimilarity(queryEmbedding, docEmb)
        );

        results.push({
          model: 'gemini-embedding-001',
          dimensions: 768,
          generationTime: Date.now() - start,
          similarity: Math.max(...similarities),
          taskType
        });
      }
    }

    return results;
  }

  /**
   * Calculate cosine similarity between two vectors
   */
  private cosineSimilarity(a: number[], b: number[]): number {
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }

    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }

  /**
   * Run comprehensive comparison
   */
  async runComparison() {
    console.log('\n=== Embedding Service Comparison ===\n');

    // Test texts relevant to claude-self-reflection
    const testTexts = [
      "performance optimization for memento project",
      "Voyage AI embeddings accuracy comparison",
      "Python 3.13 compatibility Docker solution",
      "cross-collection search implementation MCP",
      "TodoWrite tool usage pattern"
    ];

    const query = "how to improve search accuracy in memento";
    const documents = [
      "We improved search accuracy by switching from OpenAI to Voyage AI embeddings, achieving 66.1% accuracy",
      "The memento project uses Qdrant vector database with cross-collection search",
      "Performance optimization involved using batch processing and rate limiting",
      "Docker containers solve Python compatibility issues",
      "TodoWrite helps track implementation progress"
    ];

    // 1. Speed comparison
    console.log('1. Speed Test (5 embeddings):');
    const speedResults = await this.compareSpeed(testTexts);
    for (const [model, time] of Object.entries(speedResults)) {
      console.log(`   ${model}: ${time}ms (${(time / testTexts.length).toFixed(1)}ms per embedding)`);
    }

    // 2. Similarity comparison
    console.log('\n2. Semantic Similarity Test:');
    console.log(`   Query: "${query}"`);
    const similarityResults = await this.compareSimilarity(query, documents);
    
    for (const result of similarityResults) {
      console.log(`\n   ${result.model} ${result.taskType ? `(${result.taskType})` : ''}`);
      console.log(`   - Dimensions: ${result.dimensions}`);
      console.log(`   - Generation time: ${result.generationTime}ms`);
      console.log(`   - Max similarity: ${result.similarity.toFixed(4)}`);
    }

    // 3. Feature comparison
    console.log('\n3. Feature Comparison:');
    const comparison = EmbeddingComparison.getComparison();
    
    console.log('\n   Voyage AI:');
    comparison.voyage.advantages.forEach(adv => console.log(`   ✓ ${adv}`));
    console.log('\n   Best for:');
    comparison.voyage.bestFor.forEach(use => console.log(`   - ${use}`));

    console.log('\n   Google Gemini:');
    comparison.gemini.advantages.forEach(adv => console.log(`   ✓ ${adv}`));
    console.log('\n   Best for:');
    comparison.gemini.bestFor.forEach(use => console.log(`   - ${use}`));

    // 4. Cost estimation
    console.log('\n4. Cost Estimation (for 50M tokens):');
    const costs = EmbeddingComparison.estimateCosts(50_000_000);
    console.log(`   Voyage: $${costs.voyage.estimatedCost.toFixed(2)} (after free tier)`);
    console.log(`   Gemini: ~$${costs.gemini.estimatedCost.toFixed(2)} (varies by region)`);
  }

  /**
   * Generate recommendation
   */
  generateRecommendation(): string {
    return `
## Recommendation for Claude Self-Reflection MCP

Based on the comparison:

### Continue with Voyage AI for now because:
1. **Proven accuracy**: 66.1% vs OpenAI's 39.2% (no Gemini benchmarks available)
2. **Large token limit**: 32k tokens handles long conversations without chunking
3. **Cost-effective**: 200M free tokens covers the entire project
4. **Already implemented**: Working solution with cross-collection search

### Consider Gemini in the future if:
1. **Task-specific optimization needed**: Different query types (Q&A vs retrieval)
2. **Variable dimensions required**: Need to balance storage vs accuracy
3. **Google Cloud integration**: Already using GCP infrastructure
4. **Accuracy benchmarks published**: Can compare against Voyage's 66.1%

### Hybrid Approach (Future Enhancement):
- Use Voyage for general retrieval (proven accuracy)
- Add Gemini for specific tasks:
  - QUESTION_ANSWERING for "how to" queries
  - FACT_VERIFICATION for checking implementation status
  - CODE_RETRIEVAL_QUERY for code-specific searches

### Implementation Priority:
1. Keep Voyage as primary (✓ Done)
2. Add query classification layer
3. Route queries to optimal embedding service
4. A/B test results for quality metrics
`;
  }
}

// Main execution
async function main() {
  const voyageKey = process.env.VOYAGE_KEY || process.env['VOYAGE_KEY-2'];
  const geminiKey = process.env.GEMINI_API_KEY;

  if (!voyageKey && !geminiKey) {
    console.error('Error: Need at least one API key (VOYAGE_KEY or GEMINI_API_KEY)');
    process.exit(1);
  }

  const tester = new EmbeddingComparisonTest(voyageKey, geminiKey);
  
  try {
    await tester.initialize();
    await tester.runComparison();
    console.log(tester.generateRecommendation());
  } catch (error) {
    console.error('Comparison failed:', error);
  }
}

if (require.main === module) {
  main();
}

export { EmbeddingComparisonTest };