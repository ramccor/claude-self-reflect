#!/usr/bin/env node
import { spawn } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Test MCP server with sample queries
async function testMCP() {
  console.log('Testing Claude Self-Reflection MCP Server...\n');

  const mcp = spawn('node', [join(__dirname, 'dist', 'index.js')], {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: {
      ...process.env,
      QDRANT_URL: 'http://localhost:6333',
      ISOLATION_MODE: 'isolated',
      ALLOW_CROSS_PROJECT: 'false',
      PREFER_LOCAL_EMBEDDINGS: 'true'
    }
  });

  let responseBuffer = '';
  let errorBuffer = '';

  mcp.stdout.on('data', (data) => {
    responseBuffer += data.toString();
  });

  mcp.stderr.on('data', (data) => {
    errorBuffer += data.toString();
  });

  // Test 1: List tools
  console.log('1. Testing tools/list...');
  mcp.stdin.write(JSON.stringify({
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/list'
  }) + '\n');

  await new Promise(resolve => setTimeout(resolve, 1000));

  // Test 2: Search for Qdrant migration
  console.log('\n2. Testing reflect_on_past for "Qdrant migration"...');
  mcp.stdin.write(JSON.stringify({
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'reflect_on_past',
      arguments: {
        query: 'Qdrant migration project isolation',
        limit: 3,
        minScore: 0.5
      }
    }
  }) + '\n');

  await new Promise(resolve => setTimeout(resolve, 2000));

  // Test 3: Cross-project search (should fail)
  console.log('\n3. Testing cross-project search (should be blocked)...');
  mcp.stdin.write(JSON.stringify({
    jsonrpc: '2.0',
    id: 3,
    method: 'tools/call',
    params: {
      name: 'reflect_on_past',
      arguments: {
        query: 'any conversation',
        crossProject: true,
        limit: 3
      }
    }
  }) + '\n');

  await new Promise(resolve => setTimeout(resolve, 2000));

  // Parse and display results
  console.log('\n=== RESULTS ===\n');
  console.log('Stderr output:');
  console.log(errorBuffer);
  
  console.log('\nStdout responses:');
  const responses = responseBuffer.split('\n').filter(line => line.trim());
  responses.forEach((response, i) => {
    try {
      const parsed = JSON.parse(response);
      console.log(`\nResponse ${i + 1}:`);
      console.log(JSON.stringify(parsed, null, 2));
    } catch (e) {
      console.log(`Raw response ${i + 1}: ${response}`);
    }
  });

  mcp.kill();
}

testMCP().catch(console.error);