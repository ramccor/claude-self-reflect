#!/usr/bin/env node
/**
 * Quick test to compare Gemini vs Voyage embeddings
 */

import fetch from 'node-fetch';

const VOYAGE_API_KEY = process.env.VOYAGE_KEY;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

async function getVoyageEmbedding(text) {
  const response = await fetch('https://api.voyageai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${VOYAGE_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      input: [text],
      model: 'voyage-3.5-lite',
      input_type: 'query'
    })
  });

  const data = await response.json();
  return data.data[0].embedding;
}

async function getGeminiEmbedding(text, taskType = 'RETRIEVAL_QUERY') {
  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key=${GEMINI_API_KEY}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'models/gemini-embedding-001',
        content: {
          parts: [{ text }]
        },
        taskType: taskType,
        outputDimensionality: 768
      }),
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Gemini API error: ${response.status} - ${error}`);
  }

  const data = await response.json();
  return data.embedding.values;
}

function cosineSimilarity(a, b) {
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

async function main() {
  console.log('=== Gemini vs Voyage Embedding Comparison ===\n');

  const testQuery = "how to improve search accuracy in memento project";
  const testDocuments = [
    "We improved search accuracy by switching from OpenAI to Voyage AI embeddings, achieving 66.1% accuracy",
    "The memento project uses Qdrant vector database with cross-collection search functionality",
    "Performance optimization involved batch processing and proper rate limiting strategies"
  ];

  try {
    // Test Voyage
    console.log('1. Testing Voyage AI:');
    const voyageStart = Date.now();
    const voyageQueryEmb = await getVoyageEmbedding(testQuery);
    const voyageDocEmbs = await Promise.all(testDocuments.map(doc => getVoyageEmbedding(doc)));
    const voyageTime = Date.now() - voyageStart;

    console.log(`   - Dimensions: ${voyageQueryEmb.length}`);
    console.log(`   - Generation time: ${voyageTime}ms`);
    
    const voyageScores = voyageDocEmbs.map((emb, i) => ({
      doc: i + 1,
      score: cosineSimilarity(voyageQueryEmb, emb)
    }));
    
    console.log('   - Similarity scores:');
    voyageScores.forEach(s => console.log(`     Doc ${s.doc}: ${s.score.toFixed(4)}`));

    // Test Gemini with different task types
    const taskTypes = ['RETRIEVAL_QUERY', 'SEMANTIC_SIMILARITY', 'QUESTION_ANSWERING'];
    
    // Add delay between requests to respect rate limits
    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
    
    for (const taskType of taskTypes) {
      console.log(`\n2. Testing Gemini (${taskType}):`);
      try {
        const geminiStart = Date.now();
        const geminiQueryEmb = await getGeminiEmbedding(testQuery, taskType);
        
        // Add delay between API calls
        await delay(1000);
        
        const geminiDocEmbs = [];
        for (const doc of testDocuments) {
          geminiDocEmbs.push(await getGeminiEmbedding(doc, 'RETRIEVAL_DOCUMENT'));
          await delay(1000); // Delay between each embedding
        }
        
        const geminiTime = Date.now() - geminiStart;

        console.log(`   - Dimensions: ${geminiQueryEmb.length}`);
        console.log(`   - Generation time: ${geminiTime}ms`);
        
        const geminiScores = geminiDocEmbs.map((emb, i) => ({
          doc: i + 1,
          score: cosineSimilarity(geminiQueryEmb, emb)
        }));
        
        console.log('   - Similarity scores:');
        geminiScores.forEach(s => console.log(`     Doc ${s.doc}: ${s.score.toFixed(4)}`));
      } catch (error) {
        console.log(`   - Error: ${error.message}`);
        console.log('   - Note: Gemini has strict rate limits on the free tier');
      }
    }

    // Summary
    console.log('\n=== Summary ===');
    console.log('\nVoyage AI Advantages:');
    console.log('- Higher token limit (32k vs unclear for Gemini)');
    console.log('- Proven accuracy benchmark (66.1%)');
    console.log('- Cost-effective with 200M free tokens');
    console.log('- Already implemented and working');
    
    console.log('\nGemini Advantages:');
    console.log('- Task-specific optimization');
    console.log('- Variable dimensions (768, 1536, 3072)');
    console.log('- May provide better results for specific query types');
    console.log('- Google infrastructure and ecosystem');
    
    console.log('\nRecommendation:');
    console.log('Continue with Voyage AI for now. Consider Gemini for:');
    console.log('- Question-answering specific queries');
    console.log('- When you need variable dimensions');
    console.log('- Future A/B testing to compare real-world accuracy');

  } catch (error) {
    console.error('Error:', error.message);
  }
}

main().catch(console.error);