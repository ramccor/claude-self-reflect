#!/usr/bin/env node
import { spawn } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = dirname(__dirname);

// ANSI color codes for output
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

async function testMCPDecay() {
  console.log(`${colors.cyan}🧪 Testing Memory Decay through MCP Protocol${colors.reset}\n`);

  // Start the MCP server using the run-mcp.sh script
  const mcp = spawn('/bin/bash', [join(PROJECT_ROOT, 'claude-self-reflection', 'run-mcp.sh')], {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: {
      ...process.env,
      // Ensure these are set for testing
      ENABLE_MEMORY_DECAY: 'true',
      DECAY_WEIGHT: '0.3',
      DECAY_SCALE_DAYS: '90'
    }
  });

  let responseBuffer = '';
  let errorBuffer = '';
  let requestId = 0;

  mcp.stdout.on('data', (data) => {
    responseBuffer += data.toString();
  });

  mcp.stderr.on('data', (data) => {
    errorBuffer += data.toString();
  });

  // Helper to send request and wait for response
  async function sendRequest(method, params = {}) {
    const id = ++requestId;
    const request = {
      jsonrpc: '2.0',
      id,
      method,
      params
    };

    console.log(`${colors.blue}→ Sending: ${method}${colors.reset}`);
    mcp.stdin.write(JSON.stringify(request) + '\n');

    // Wait for response
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Parse latest response
    const lines = responseBuffer.split('\n').filter(line => line.trim());
    for (let i = lines.length - 1; i >= 0; i--) {
      try {
        const response = JSON.parse(lines[i]);
        if (response.id === id) {
          return response;
        }
      } catch (e) {
        // Continue to next line
      }
    }
    return null;
  }

  // Wait for server to start
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Step 1: List available tools
  console.log(`${colors.yellow}📋 Step 1: Listing available tools${colors.reset}`);
  const toolsResponse = await sendRequest('tools/list');
  
  if (toolsResponse && toolsResponse.result && toolsResponse.result.tools) {
    console.log(`Found ${toolsResponse.result.tools.length} tools:`);
    toolsResponse.result.tools.forEach(tool => {
      console.log(`  - ${colors.green}${tool.name}${colors.reset}: ${tool.description}`);
    });
  }

  // Step 2: Test search WITHOUT decay
  console.log(`\n${colors.yellow}📋 Step 2: Search WITHOUT memory decay${colors.reset}`);
  const noDecayResponse = await sendRequest('tools/call', {
    name: 'reflect_on_past',
    arguments: {
      query: 'qdrant',
      limit: 5,
      minScore: 0,
      useDecay: false
    }
  });

  let noDecayResults = [];
  if (noDecayResponse && noDecayResponse.result && noDecayResponse.result.content) {
    const content = noDecayResponse.result.content[0].text;
    console.log(`\n${colors.magenta}Results without decay:${colors.reset}`);
    
    // Parse results from the text response
    const scoreMatches = [...content.matchAll(/Score: ([\d.]+)/g)];
    const timeMatches = [...content.matchAll(/Time: ([\d-T:]+)/g)];
    
    for (let i = 0; i < scoreMatches.length; i++) {
      const score = parseFloat(scoreMatches[i][1]);
      const time = timeMatches[i] ? timeMatches[i][1] : 'Unknown';
      const age = time !== 'Unknown' ? Math.floor((Date.now() - new Date(time).getTime()) / (1000 * 60 * 60 * 24)) : '?';
      
      noDecayResults.push({ score, time, age });
      console.log(`  Result ${i + 1}: Score=${score.toFixed(3)}, Age=${age} days`);
    }
  }

  // Step 3: Test search WITH decay
  console.log(`\n${colors.yellow}📋 Step 3: Search WITH memory decay${colors.reset}`);
  const withDecayResponse = await sendRequest('tools/call', {
    name: 'reflect_on_past',
    arguments: {
      query: 'qdrant',
      limit: 5,
      minScore: 0,
      useDecay: true
    }
  });

  let withDecayResults = [];
  if (withDecayResponse && withDecayResponse.result && withDecayResponse.result.content) {
    const content = withDecayResponse.result.content[0].text;
    console.log(`\n${colors.magenta}Results with decay:${colors.reset}`);
    
    // Parse results
    const scoreMatches = [...content.matchAll(/Score: ([\d.]+)/g)];
    const timeMatches = [...content.matchAll(/Time: ([\d-T:]+)/g)];
    
    for (let i = 0; i < scoreMatches.length; i++) {
      const score = parseFloat(scoreMatches[i][1]);
      const time = timeMatches[i] ? timeMatches[i][1] : 'Unknown';
      const age = time !== 'Unknown' ? Math.floor((Date.now() - new Date(time).getTime()) / (1000 * 60 * 60 * 24)) : '?';
      
      withDecayResults.push({ score, time, age });
      console.log(`  Result ${i + 1}: Score=${score.toFixed(3)}, Age=${age} days`);
    }
  }

  // Step 4: Compare results
  console.log(`\n${colors.yellow}📊 Comparison Summary${colors.reset}`);
  
  if (noDecayResults.length > 0 && withDecayResults.length > 0) {
    const avgAgeNoDecay = noDecayResults.reduce((sum, r) => sum + (r.age === '?' ? 0 : r.age), 0) / noDecayResults.length;
    const avgAgeWithDecay = withDecayResults.reduce((sum, r) => sum + (r.age === '?' ? 0 : r.age), 0) / withDecayResults.length;
    
    console.log(`\nAverage age of results:`);
    console.log(`  Without decay: ${avgAgeNoDecay.toFixed(0)} days`);
    console.log(`  With decay: ${avgAgeWithDecay.toFixed(0)} days`);
    
    if (avgAgeWithDecay < avgAgeNoDecay) {
      const improvement = ((avgAgeNoDecay - avgAgeWithDecay) / avgAgeNoDecay * 100).toFixed(0);
      console.log(`  ${colors.green}✨ Improvement: ${improvement}% more recent!${colors.reset}`);
    }
    
    // Check if scores are different
    const scoresChanged = noDecayResults.some((r, i) => 
      withDecayResults[i] && Math.abs(r.score - withDecayResults[i].score) > 0.001
    );
    
    if (scoresChanged) {
      console.log(`\n${colors.green}✅ Memory decay is working! Scores have been adjusted based on age.${colors.reset}`);
    } else {
      console.log(`\n${colors.red}⚠️  Scores appear unchanged. Check if decay is properly configured.${colors.reset}`);
    }
  }

  // Debug info
  console.log(`\n${colors.yellow}🐛 Debug Information${colors.reset}`);
  console.log('Environment variables:');
  console.log(`  ENABLE_MEMORY_DECAY: ${process.env.ENABLE_MEMORY_DECAY || 'not set'}`);
  console.log(`  DECAY_WEIGHT: ${process.env.DECAY_WEIGHT || 'not set'}`);
  console.log(`  DECAY_SCALE_DAYS: ${process.env.DECAY_SCALE_DAYS || 'not set'}`);
  
  if (errorBuffer) {
    console.log('\nServer stderr output:');
    console.log(errorBuffer.split('\n').slice(0, 20).join('\n'));
  }

  // Cleanup
  mcp.kill();
  process.exit(0);
}

// Run the test
testMCPDecay().catch(error => {
  console.error(`${colors.red}Error:${colors.reset}`, error);
  process.exit(1);
});