#!/usr/bin/env node
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { readFileSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Handle command line arguments
const args = process.argv.slice(2);
const command = args[0];

if (command === 'setup') {
  // Run the setup wizard
  const setupPath = join(__dirname, '..', 'scripts', 'setup-wizard.js');
  const child = spawn('node', [setupPath], {
    stdio: 'inherit'
  });

  child.on('error', (error) => {
    console.error('Failed to start setup wizard:', error);
    process.exit(1);
  });

  child.on('exit', (code) => {
    process.exit(code || 0);
  });
} else if (command === '--version' || command === '-v') {
  // Read package.json to get version
  const packagePath = join(__dirname, '..', 'package.json');
  const pkg = JSON.parse(readFileSync(packagePath, 'utf8'));
  console.log(pkg.version);
} else if (command === '--help' || command === '-h' || !command) {
  console.log(`
Claude Self-Reflect - Give Claude perfect memory of all your conversations

Usage:
  claude-self-reflect <command>

Commands:
  setup      Run the interactive setup wizard
  
Options:
  --version  Show version number
  --help     Show this help message

Examples:
  claude-self-reflect setup    # Run interactive setup
  npx claude-self-reflect setup  # Run without installing globally
`);
} else {
  console.error(`Unknown command: ${command}`);
  console.error('Run "claude-self-reflect --help" for usage information');
  process.exit(1);
}