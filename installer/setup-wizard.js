#!/usr/bin/env node

import { execSync, spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs/promises';
import readline from 'readline';
import path from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = join(__dirname, '..');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

const question = (query) => new Promise((resolve) => rl.question(query, resolve));

async function checkPython() {
  console.log('\n📦 Checking Python installation...');
  try {
    const version = execSync('python3 --version').toString().trim();
    console.log(`✅ Found ${version}`);
    return true;
  } catch {
    console.log('❌ Python 3.10+ not found');
    console.log('   Please install Python from https://python.org');
    return false;
  }
}

async function checkQdrant() {
  console.log('\n🐳 Checking Qdrant...');
  try {
    const response = await fetch('http://localhost:6333/health');
    if (response.ok) {
      console.log('✅ Qdrant is already running');
      return true;
    }
  } catch {}
  
  console.log('❌ Qdrant not found');
  const start = await question('Would you like to start Qdrant with Docker? (y/n): ');
  
  if (start.toLowerCase() === 'y') {
    try {
      console.log('Starting Qdrant...');
      execSync('docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest', { stdio: 'inherit' });
      console.log('✅ Qdrant started successfully');
      return true;
    } catch (error) {
      console.log('❌ Failed to start Qdrant. Please install Docker first.');
      return false;
    }
  }
  
  return false;
}

async function setupPythonEnvironment() {
  console.log('\n🐍 Setting up Python MCP server...');
  
  const mcpPath = join(projectRoot, 'mcp-server');
  
  try {
    // Create virtual environment
    console.log('Creating virtual environment...');
    execSync(`cd "${mcpPath}" && python3 -m venv venv`, { stdio: 'inherit' });
    
    // Install dependencies
    console.log('Installing dependencies...');
    const activateCmd = process.platform === 'win32' 
      ? 'venv\\Scripts\\activate' 
      : 'source venv/bin/activate';
    
    execSync(`cd "${mcpPath}" && ${activateCmd} && pip install -e .`, { 
      stdio: 'inherit',
      shell: true 
    });
    
    console.log('✅ Python environment setup complete');
    return true;
  } catch (error) {
    console.log('❌ Failed to setup Python environment:', error.message);
    return false;
  }
}

async function configureEnvironment() {
  console.log('\n🔐 Configuring environment variables...');
  
  const envPath = join(projectRoot, '.env');
  let envContent = '';
  
  try {
    envContent = await fs.readFile(envPath, 'utf-8');
  } catch {
    // .env doesn't exist, create it
  }
  
  // Check for VOYAGE_KEY
  if (!envContent.includes('VOYAGE_KEY=') || envContent.includes('VOYAGE_KEY=your-')) {
    console.log('\nVoyage AI provides embeddings for semantic search.');
    console.log('Get your free API key at: https://www.voyageai.com/');
    
    const voyageKey = await question('Enter your Voyage AI API key (or press Enter to skip): ');
    
    if (voyageKey) {
      envContent = envContent.replace(/VOYAGE_KEY=.*/g, '');
      envContent += `\nVOYAGE_KEY=${voyageKey}\n`;
    }
  }
  
  // Set default Qdrant URL if not present
  if (!envContent.includes('QDRANT_URL=')) {
    envContent += 'QDRANT_URL=http://localhost:6333\n';
  }
  
  await fs.writeFile(envPath, envContent.trim() + '\n');
  console.log('✅ Environment configured');
}

async function setupClaude() {
  console.log('\n🤖 Claude Code MCP Configuration...');
  
  const runScript = join(projectRoot, 'mcp-server', 'run-mcp.sh');
  
  console.log('\nAdd this to your Claude Code settings:');
  console.log('```bash');
  console.log(`claude mcp add claude-self-reflect "${runScript}" -e VOYAGE_KEY="<your-key>" -e QDRANT_URL="http://localhost:6333"`);
  console.log('```');
  
  console.log('\nThen restart Claude Code for the changes to take effect.');
}

async function installAgents() {
  console.log('\n🤖 Installing Claude agents...');
  
  const agentsSource = join(projectRoot, '.claude', 'agents');
  const agentsDest = join(process.cwd(), '.claude', 'agents');
  
  if (agentsSource === agentsDest) {
    console.log('📦 Skipping agent installation in package directory');
    return;
  }
  
  try {
    await fs.mkdir(path.dirname(agentsDest), { recursive: true });
    
    // Check if already exists
    try {
      await fs.access(agentsDest);
      console.log('✅ Agents already installed');
      return;
    } catch {
      // Copy agents
      await fs.cp(agentsSource, agentsDest, { recursive: true });
      console.log('✅ Agents installed to .claude/agents/');
    }
  } catch (error) {
    console.log('⚠️  Could not install agents:', error.message);
  }
}

async function main() {
  console.log('🚀 Welcome to Claude Self-Reflect Setup!\n');
  console.log('This wizard will help you set up conversation memory for Claude.\n');
  
  // Check prerequisites
  const pythonOk = await checkPython();
  if (!pythonOk) {
    console.log('\n❌ Setup cannot continue without Python');
    process.exit(1);
  }
  
  const qdrantOk = await checkQdrant();
  if (!qdrantOk) {
    console.log('\n⚠️  Qdrant is required for the vector database');
  }
  
  // Setup Python environment
  await setupPythonEnvironment();
  
  // Configure environment
  await configureEnvironment();
  
  // Install agents
  await installAgents();
  
  // Show Claude configuration
  await setupClaude();
  
  console.log('\n✅ Setup complete!');
  console.log('\nNext steps:');
  console.log('1. Import your conversations: cd scripts && python import-conversations-voyage.py');
  console.log('2. Use the reflection tools in Claude Code');
  console.log('\nFor more info: https://github.com/ramakay/claude-self-reflect');
  
  rl.close();
}

main().catch(console.error);