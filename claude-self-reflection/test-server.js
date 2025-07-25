import { spawn } from 'child_process';

console.log('Testing Claude Self-Reflection MCP Server...\n');

// Start the MCP server
const server = spawn('node', ['dist/index.js'], {
  stdio: ['pipe', 'pipe', 'inherit']
});

// Send initialization request
const initRequest = {
  jsonrpc: '2.0',
  id: 1,
  method: 'initialize',
  params: {
    protocolVersion: '0.1.0',
    capabilities: {},
    clientInfo: {
      name: 'test-client',
      version: '1.0.0'
    }
  }
};

// Send list tools request after initialization
const listToolsRequest = {
  jsonrpc: '2.0',
  id: 2,
  method: 'tools/list',
  params: {}
};

// Send test search request
const searchRequest = {
  jsonrpc: '2.0',
  id: 3,
  method: 'tools/call',
  params: {
    name: 'reflect_on_past',
    arguments: {
      query: 'neo4j qdrant',
      limit: 3
    }
  }
};

let buffer = '';

server.stdout.on('data', (data) => {
  buffer += data.toString();
  
  // Try to parse complete JSON-RPC messages
  const lines = buffer.split('\n');
  buffer = lines.pop() || '';
  
  for (const line of lines) {
    if (line.trim()) {
      try {
        const response = JSON.parse(line);
        console.log('Response:', JSON.stringify(response, null, 2));
        
        // Handle different responses
        if (response.id === 1) {
          console.log('\n✅ Server initialized successfully\n');
          // Send list tools request
          server.stdin.write(JSON.stringify(listToolsRequest) + '\n');
        } else if (response.id === 2) {
          console.log('\n✅ Tools listed successfully\n');
          // Send search request
          server.stdin.write(JSON.stringify(searchRequest) + '\n');
        } else if (response.id === 3) {
          console.log('\n✅ Search completed successfully\n');
          // Exit
          process.exit(0);
        }
      } catch (e) {
        console.error('Failed to parse response:', e);
      }
    }
  }
});

// Send initialization
setTimeout(() => {
  console.log('Sending initialization request...\n');
  server.stdin.write(JSON.stringify(initRequest) + '\n');
}, 100);

// Timeout after 10 seconds
setTimeout(() => {
  console.error('\n❌ Test timed out');
  process.exit(1);
}, 10000);