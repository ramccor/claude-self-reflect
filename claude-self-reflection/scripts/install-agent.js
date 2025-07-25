#!/usr/bin/env node

import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function installAgent() {
  try {
    // Get the current working directory (where npm install was run)
    const cwd = process.cwd();
    
    // Check if we're in the package directory itself (during development)
    if (cwd.includes('claude-self-reflection')) {
      console.log('📦 Skipping agent installation in package directory');
      return;
    }
    
    // Define paths
    const agentSource = path.join(__dirname, '..', 'agents', 'reflection.md');
    const claudeDir = path.join(cwd, '.claude');
    const agentsDir = path.join(claudeDir, 'agents');
    const agentDest = path.join(agentsDir, 'reflection.md');
    
    // Check if source file exists
    try {
      await fs.access(agentSource);
    } catch {
      console.log('⚠️  Reflection agent source file not found, skipping installation');
      return;
    }
    
    // Create directories if they don't exist
    await fs.mkdir(claudeDir, { recursive: true });
    await fs.mkdir(agentsDir, { recursive: true });
    
    // Check if agent already exists
    try {
      await fs.access(agentDest);
      console.log('✅ Reflection agent already installed at .claude/agents/reflection.md');
      return;
    } catch {
      // File doesn't exist, proceed with installation
    }
    
    // Copy the agent file
    await fs.copyFile(agentSource, agentDest);
    
    console.log('✅ Reflection agent installed at .claude/agents/reflection.md');
    console.log('💡 The agent will activate when you ask about past conversations');
    console.log('   Example: "What did we discuss about API design?"');
    console.log('   Or explicitly: "Use the reflection agent to find..."');
    
  } catch (error) {
    console.error('❌ Error installing reflection agent:', error.message);
    // Don't fail the entire install if agent installation fails
    process.exit(0);
  }
}

// Run the installation
installAgent();