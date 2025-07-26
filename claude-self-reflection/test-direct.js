#!/usr/bin/env node

// Direct test of the MCP functionality
import fetch from 'node-fetch';

const QDRANT_URL = 'http://localhost:6333';

async function testQdrant() {
  try {
    // Check collections
    const collectionsResponse = await fetch(`${QDRANT_URL}/collections`);
    const collections = await collectionsResponse.json();
    
    const voyageCollections = collections.result.collections
      .filter(c => c.name.endsWith('_voyage'));
    
    console.log(`Found ${voyageCollections.length} Voyage collections`);
    
    // Check a sample collection
    const sampleCollection = voyageCollections[0].name;
    const pointsResponse = await fetch(`${QDRANT_URL}/collections/${sampleCollection}/points/scroll`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit: 1, with_payload: true, with_vector: false })
    });
    
    const points = await pointsResponse.json();
    if (points.result && points.result.points && points.result.points.length > 0) {
      console.log('\nSample point from', sampleCollection);
      console.log('Payload keys:', Object.keys(points.result.points[0].payload));
      console.log('Sample payload:', points.result.points[0].payload);
    }
  } catch (error) {
    console.error('Error:', error);
  }
}

testQdrant();