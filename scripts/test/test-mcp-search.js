#\!/usr/bin/env node

const { spawn } = require('child_process');

const mcp = spawn('./claude-self-reflection/run-mcp.sh');

let messageBuffer = '';
let initialized = false;

mcp.stdout.on('data', (data) => {
  messageBuffer += data.toString();
  
  // Try to parse complete messages
  const lines = messageBuffer.split('\n');
  messageBuffer = lines.pop() || '';
  
  lines.forEach(line => {
    if (line.trim()) {
      try {
        const message = JSON.parse(line);
        console.log('Received:', JSON.stringify(message, null, 2));
        
        // Handle initialization response
        if (message.id === 1 && message.result) {
          initialized = true;
          console.log('\n✅ MCP server initialized successfully');
          
          // Now send the search request
          sendSearchRequest();
        }
        
        // Handle search response
        if (message.id === 2 && message.result) {
          console.log('\n🔍 Search Results:');
          console.log('Found', message.result.content.length, 'results');
          message.result.content.forEach((item, i) => {
            console.log(`\n--- Result ${i + 1} ---`);
            console.log('Score:', item.score);
            console.log('Content:', item.content.substring(0, 200) + '...');
            if (item.metadata) {
              console.log('File:', item.metadata.source_file);
              console.log('Date:', item.metadata.timestamp);
            }
          });
          
          // Exit after displaying results
          setTimeout(() => process.exit(0), 100);
        }
      } catch (e) {
        // Not a complete JSON message
      }
    }
  });
});

mcp.stderr.on('data', (data) => {
  console.error('Debug:', data.toString());
});

// Send initialization
console.log('🚀 Initializing MCP server...');
const initRequest = {
  jsonrpc: '2.0',
  id: 1,
  method: 'initialize',
  params: {
    protocolVersion: '2024-11-05',
    capabilities: {},
    clientInfo: { name: 'test-search', version: '1.0' }
  }
};
mcp.stdin.write(JSON.stringify(initRequest) + '\n');

function sendSearchRequest() {
  console.log('\n🔍 Searching for "streaming importer fixes"...');
  const searchRequest = {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'reflect_on_past',
      arguments: {
        query: 'streaming importer fixes',
        limit: 5,
        crossProject: true,
        minScore: 0.7,
        useDecay: true
      }
    }
  };
  mcp.stdin.write(JSON.stringify(searchRequest) + '\n');
}

// Timeout after 10 seconds
setTimeout(() => {
  console.log('\n⏱️ Timeout - closing connection');
  mcp.kill();
  process.exit(1);
}, 10000);
