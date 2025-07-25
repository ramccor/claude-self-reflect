#!/usr/bin/env node
import { QdrantClient } from '@qdrant/js-client-rest';

const QDRANT_URL = 'http://localhost:6333';

async function testSearch() {
  const client = new QdrantClient({ url: QDRANT_URL });
  
  // Get collection info
  const collectionInfo = await client.getCollection('conversations');
  console.log('Collection info:', JSON.stringify(collectionInfo, null, 2));
  
  // Scroll through some points to see what's there
  const scrollResult = await client.scroll('conversations', {
    limit: 5,
    with_payload: true,
    with_vector: false
  });
  
  console.log('\nSample points:');
  scrollResult.points.forEach((point, i) => {
    console.log(`\nPoint ${i + 1}:`);
    console.log('ID:', point.id);
    console.log('Project:', point.payload?.project_id);
    console.log('Text preview:', point.payload?.text?.substring(0, 100) + '...');
  });
  
  // Try a direct vector search with a dummy vector
  console.log('\nTrying vector search with dummy vector...');
  const dummyVector = new Array(384).fill(0.1);
  
  try {
    const searchResult = await client.search('conversations', {
      vector: dummyVector,
      limit: 3,
      with_payload: true
    });
    
    console.log('\nSearch results:');
    searchResult.forEach((result, i) => {
      console.log(`\nResult ${i + 1}:`);
      console.log('Score:', result.score);
      console.log('Text preview:', result.payload?.text?.substring(0, 100) + '...');
    });
  } catch (error) {
    console.error('Search error:', error);
  }
}

testSearch().catch(console.error);