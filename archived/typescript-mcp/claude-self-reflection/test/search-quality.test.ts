#!/usr/bin/env node
/**
 * Comprehensive test suite for search quality validation
 * Tests various query types, score thresholds, and cross-collection functionality
 */

import { QdrantClient } from '@qdrant/js-client-rest';
import { createEmbeddingService } from '../src/embeddings';

// Test configuration
const QDRANT_URL = process.env.QDRANT_URL || 'http://localhost:6333';
const VOYAGE_API_KEY = process.env.VOYAGE_KEY || process.env['VOYAGE_KEY-2'];

interface TestQuery {
  query: string;
  intent: 'technical' | 'temporal' | 'conceptual' | 'specific' | 'broad';
  expectedKeywords: string[];
  minScore: number;
}

interface TestResult {
  query: string;
  found: boolean;
  topScore: number;
  relevantResults: number;
  executionTime: number;
  errors?: string[];
}

class SearchQualityTester {
  private qdrantClient: QdrantClient;
  private embeddingService: any;
  private voyageCollections: string[] = [];

  constructor() {
    this.qdrantClient = new QdrantClient({ url: QDRANT_URL });
  }

  async initialize() {
    // Initialize embedding service
    this.embeddingService = await createEmbeddingService({
      voyageApiKey: VOYAGE_API_KEY,
    });

    // Get all Voyage collections
    const collections = await this.qdrantClient.getCollections();
    this.voyageCollections = collections.collections
      .map(c => c.name)
      .filter(name => name.endsWith('_voyage'));

    console.log(`Found ${this.voyageCollections.length} Voyage collections for testing`);
  }

  /**
   * Define comprehensive test queries covering different search intents
   */
  getTestQueries(): TestQuery[] {
    return [
      // Technical queries
      {
        query: "performance optimization memento project",
        intent: 'technical',
        expectedKeywords: ['performance', 'optimization', 'memento'],
        minScore: 0.5
      },
      {
        query: "Docker configuration Python 3.13 compatibility",
        intent: 'technical',
        expectedKeywords: ['Docker', 'Python', 'compatibility'],
        minScore: 0.5
      },
      {
        query: "API rate limits Voyage 3 RPM 60 RPM",
        intent: 'technical',
        expectedKeywords: ['rate', 'limit', 'RPM', 'Voyage'],
        minScore: 0.6
      },
      {
        query: "Qdrant vector database embedding dimensions",
        intent: 'technical',
        expectedKeywords: ['Qdrant', 'vector', 'embedding', 'dimensions'],
        minScore: 0.5
      },

      // Temporal queries
      {
        query: "what did we implement yesterday",
        intent: 'temporal',
        expectedKeywords: ['implement', 'yesterday'],
        minScore: 0.4
      },
      {
        query: "recent changes to import script",
        intent: 'temporal',
        expectedKeywords: ['recent', 'changes', 'import'],
        minScore: 0.5
      },

      // Conceptual queries
      {
        query: "why switch from OpenAI to Voyage embeddings",
        intent: 'conceptual',
        expectedKeywords: ['switch', 'OpenAI', 'Voyage', 'embeddings'],
        minScore: 0.6
      },
      {
        query: "benefits of cross-collection search",
        intent: 'conceptual',
        expectedKeywords: ['benefits', 'cross-collection', 'search'],
        minScore: 0.5
      },

      // Specific queries
      {
        query: "TodoWrite tool usage pattern",
        intent: 'specific',
        expectedKeywords: ['TodoWrite', 'tool', 'usage'],
        minScore: 0.6
      },
      {
        query: "sentencepiece build error cmake",
        intent: 'specific',
        expectedKeywords: ['sentencepiece', 'build', 'error', 'cmake'],
        minScore: 0.7
      },

      // Broad queries
      {
        query: "memento stack",
        intent: 'broad',
        expectedKeywords: ['memento', 'stack'],
        minScore: 0.4
      },
      {
        query: "Claude conversations",
        intent: 'broad',
        expectedKeywords: ['Claude', 'conversations'],
        minScore: 0.4
      }
    ];
  }

  /**
   * Test search with different score thresholds
   */
  async testScoreThresholds(query: string): Promise<Record<number, number>> {
    const thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8];
    const results: Record<number, number> = {};

    const queryEmbedding = await this.embeddingService.generateEmbedding(query);

    for (const threshold of thresholds) {
      let totalResults = 0;

      // Search across all collections with this threshold
      for (const collection of this.voyageCollections.slice(0, 3)) { // Sample 3 collections
        try {
          const searchResponse = await this.qdrantClient.search(collection, {
            vector: queryEmbedding,
            limit: 10,
            score_threshold: threshold,
            with_payload: false,
          });
          totalResults += searchResponse.length;
        } catch (error) {
          console.error(`Error searching ${collection}:`, error);
        }
      }

      results[threshold] = totalResults;
    }

    return results;
  }

  /**
   * Test cross-collection search functionality
   */
  async testCrossCollectionSearch(query: string, limit: number = 5): Promise<{
    totalResults: number;
    collectionsWithResults: number;
    topScores: number[];
  }> {
    const queryEmbedding = await this.embeddingService.generateEmbedding(query);
    let totalResults = 0;
    let collectionsWithResults = 0;
    const allScores: number[] = [];

    for (const collection of this.voyageCollections) {
      try {
        const searchResponse = await this.qdrantClient.search(collection, {
          vector: queryEmbedding,
          limit,
          score_threshold: 0.4,
          with_payload: false,
        });

        if (searchResponse.length > 0) {
          collectionsWithResults++;
          totalResults += searchResponse.length;
          allScores.push(...searchResponse.map(r => r.score));
        }
      } catch (error) {
        console.error(`Error searching ${collection}:`, error);
      }
    }

    // Sort scores and get top ones
    const topScores = allScores.sort((a, b) => b - a).slice(0, limit);

    return {
      totalResults,
      collectionsWithResults,
      topScores,
    };
  }

  /**
   * Check if results contain expected keywords
   */
  async validateResultRelevance(
    query: string,
    expectedKeywords: string[],
    limit: number = 5
  ): Promise<{ relevantCount: number; totalCount: number }> {
    const queryEmbedding = await this.embeddingService.generateEmbedding(query);
    let relevantCount = 0;
    let totalCount = 0;

    // Sample from first 3 collections
    for (const collection of this.voyageCollections.slice(0, 3)) {
      try {
        const searchResponse = await this.qdrantClient.search(collection, {
          vector: queryEmbedding,
          limit,
          score_threshold: 0.4,
          with_payload: true,
        });

        for (const result of searchResponse) {
          totalCount++;
          const text = (result.payload?.text as string || '').toLowerCase();
          
          // Check if any expected keyword is in the result
          const hasRelevantContent = expectedKeywords.some(keyword => 
            text.includes(keyword.toLowerCase())
          );
          
          if (hasRelevantContent) {
            relevantCount++;
          }
        }
      } catch (error) {
        console.error(`Error validating relevance for ${collection}:`, error);
      }
    }

    return { relevantCount, totalCount };
  }

  /**
   * Run comprehensive test suite
   */
  async runTests(): Promise<TestResult[]> {
    const testQueries = this.getTestQueries();
    const results: TestResult[] = [];

    console.log('Starting comprehensive search quality tests...\n');

    for (const testQuery of testQueries) {
      console.log(`Testing: "${testQuery.query}" (${testQuery.intent})`);
      const startTime = Date.now();
      const errors: string[] = [];

      try {
        // Test cross-collection search
        const crossCollectionResult = await this.testCrossCollectionSearch(
          testQuery.query,
          10
        );

        // Validate result relevance
        const relevanceResult = await this.validateResultRelevance(
          testQuery.query,
          testQuery.expectedKeywords,
          5
        );

        // Test score thresholds
        const thresholdResults = await this.testScoreThresholds(testQuery.query);

        const executionTime = Date.now() - startTime;

        results.push({
          query: testQuery.query,
          found: crossCollectionResult.totalResults > 0,
          topScore: crossCollectionResult.topScores[0] || 0,
          relevantResults: relevanceResult.relevantCount,
          executionTime,
        });

        // Log results
        console.log(`  ✓ Found: ${crossCollectionResult.totalResults} results`);
        console.log(`  ✓ Collections with results: ${crossCollectionResult.collectionsWithResults}/${this.voyageCollections.length}`);
        console.log(`  ✓ Top score: ${crossCollectionResult.topScores[0]?.toFixed(3) || 'N/A'}`);
        console.log(`  ✓ Relevant results: ${relevanceResult.relevantCount}/${relevanceResult.totalCount}`);
        console.log(`  ✓ Execution time: ${executionTime}ms`);
        console.log(`  ✓ Results by threshold: ${JSON.stringify(thresholdResults)}`);
        console.log('');

      } catch (error) {
        errors.push(error.message);
        results.push({
          query: testQuery.query,
          found: false,
          topScore: 0,
          relevantResults: 0,
          executionTime: Date.now() - startTime,
          errors,
        });
        console.error(`  ✗ Error: ${error.message}\n`);
      }
    }

    return results;
  }

  /**
   * Generate test report
   */
  generateReport(results: TestResult[]): void {
    console.log('\n' + '='.repeat(60));
    console.log('SEARCH QUALITY TEST REPORT');
    console.log('='.repeat(60) + '\n');

    const successfulQueries = results.filter(r => r.found && !r.errors?.length);
    const failedQueries = results.filter(r => !r.found || r.errors?.length);
    const avgExecutionTime = results.reduce((sum, r) => sum + r.executionTime, 0) / results.length;
    const avgTopScore = results.filter(r => r.topScore > 0).reduce((sum, r) => sum + r.topScore, 0) / results.filter(r => r.topScore > 0).length;

    console.log(`Total queries tested: ${results.length}`);
    console.log(`Successful queries: ${successfulQueries.length} (${(successfulQueries.length / results.length * 100).toFixed(1)}%)`);
    console.log(`Failed queries: ${failedQueries.length}`);
    console.log(`Average execution time: ${avgExecutionTime.toFixed(1)}ms`);
    console.log(`Average top score: ${avgTopScore.toFixed(3)}`);
    console.log(`Queries under 500ms: ${results.filter(r => r.executionTime < 500).length} (${(results.filter(r => r.executionTime < 500).length / results.length * 100).toFixed(1)}%)`);

    if (failedQueries.length > 0) {
      console.log('\nFailed queries:');
      failedQueries.forEach(q => {
        console.log(`  - "${q.query}": ${q.errors?.join(', ') || 'No results found'}`);
      });
    }

    console.log('\nScore distribution:');
    const scoreRanges = [
      { min: 0.8, max: 1.0, label: 'Excellent (0.8-1.0)' },
      { min: 0.6, max: 0.8, label: 'Good (0.6-0.8)' },
      { min: 0.4, max: 0.6, label: 'Fair (0.4-0.6)' },
      { min: 0, max: 0.4, label: 'Poor (0-0.4)' },
    ];

    scoreRanges.forEach(range => {
      const count = results.filter(r => r.topScore >= range.min && r.topScore < range.max).length;
      console.log(`  ${range.label}: ${count} queries`);
    });
  }
}

// Run tests if executed directly
async function main() {
  const tester = new SearchQualityTester();
  
  try {
    await tester.initialize();
    const results = await tester.runTests();
    tester.generateReport(results);
  } catch (error) {
    console.error('Test suite failed:', error);
    process.exit(1);
  }
}

// Export for use in other tests
export { SearchQualityTester, TestQuery, TestResult };

// Run tests if executed directly
main().catch(console.error);