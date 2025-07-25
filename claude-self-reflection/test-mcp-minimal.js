#!/usr/bin/env node

// Minimal test of MCP functionality
process.env.VOYAGE_KEY = 'pa-wdTYGObaxhs-XFKX2r7WCczRwEVNb9eYMTSO3yrQhZI';
process.env.QDRANT_URL = 'http://localhost:6333';

import('./dist/index.js');