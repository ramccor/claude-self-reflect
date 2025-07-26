#!/usr/bin/env node

// Test embedding generation
import { createEmbeddingService } from './dist/embeddings.js';

async function testEmbedding() {
  try {
    const embeddingService = await createEmbeddingService({
      voyageApiKey: 'pa-wdTYGObaxhs-XFKX2r7WCczRwEVNb9eYMTSO3yrQhZI'
    });
    
    console.log('Embedding service:', embeddingService.getModelName());
    console.log('Dimensions:', embeddingService.getDimensions());
    
    const testText = 'memento-mcp import stuck';
    const embedding = await embeddingService.generateEmbedding(testText);
    
    console.log('Generated embedding length:', embedding.length);
    console.log('First 5 values:', embedding.slice(0, 5));
    
  } catch (error) {
    console.error('Error:', error);
  }
}

testEmbedding();