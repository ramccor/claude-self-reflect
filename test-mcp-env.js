#!/usr/bin/env node

// Test script to verify environment variables
console.log('Environment check:');
console.log('VOYAGE_KEY:', process.env.VOYAGE_KEY ? 'Set' : 'Not set');
console.log('VOYAGE_KEY-2:', process.env['VOYAGE_KEY-2'] ? 'Set' : 'Not set');
console.log('QDRANT_URL:', process.env.QDRANT_URL);

// Load and run the MCP
require('./claude-self-reflection/dist/index.js');