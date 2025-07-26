#!/usr/bin/env node

import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Only show message if not in development
if (!process.cwd().includes('claude-self-reflect')) {
  console.log('\n🎉 Claude Self-Reflect installed!\n');
  console.log('Run "claude-self-reflect setup" to configure your installation.\n');
}