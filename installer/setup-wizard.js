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

// Parse command line arguments
const args = process.argv.slice(2);
let voyageKey = null;
let localMode = false;
let mcpConfigured = false;

for (const arg of args) {
  if (arg.startsWith('--voyage-key=')) {
    voyageKey = arg.split('=')[1];
  } else if (arg === '--local') {
    localMode = true;
  }
}

const isInteractive = process.stdin.isTTY && process.stdout.isTTY;

const rl = isInteractive ? readline.createInterface({
  input: process.stdin,
  output: process.stdout
}) : null;

const question = (query) => {
  if (!isInteractive) {
    console.log(`Non-interactive mode detected. ${query} [Defaulting to 'n']`);
    return Promise.resolve('n');
  }
  return new Promise((resolve) => rl.question(query, resolve));
};

async function checkPython() {
  console.log('\n📦 Checking Python installation...');
  try {
    const version = execSync('python3 --version').toString().trim();
    console.log(`✅ Found ${version}`);
    
    // Check if SSL module works
    try {
      execSync('python3 -c "import ssl"', { stdio: 'pipe' });
      return true;
    } catch (sslError) {
      console.log('⚠️  Python SSL module not working');
      
      // Check if we're using pyenv
      const whichPython = execSync('which python3').toString().trim();
      if (whichPython.includes('pyenv')) {
        console.log('🔍 Detected pyenv Python with broken SSL');
        
        // Check if brew Python is available
        try {
          const brewPrefix = execSync('brew --prefix python@3.11 2>/dev/null || brew --prefix python@3.10 2>/dev/null || brew --prefix python@3.12 2>/dev/null', { shell: true }).toString().trim();
          if (brewPrefix) {
            // Find the actual python executable
            let pythonPath = null;
            for (const exe of ['python3.11', 'python3.10', 'python3.12', 'python3']) {
              try {
                const fullPath = `${brewPrefix}/bin/${exe}`;
                execSync(`test -f ${fullPath}`);
                pythonPath = fullPath;
                break;
              } catch {}
            }
            
            if (pythonPath) {
              console.log(`✅ Found brew Python at ${pythonPath}`);
              // Test if SSL works with brew Python
              try {
                execSync(`${pythonPath} -c "import ssl"`, { stdio: 'pipe' });
                process.env.PYTHON_PATH = pythonPath;
                return true;
              } catch {
                console.log('⚠️  Brew Python also has SSL issues');
              }
            }
          }
        } catch {}
        
        console.log('\n🔧 Attempting to install Python with brew...');
        try {
          execSync('brew install python@3.11', { stdio: 'inherit' });
          const brewPython = execSync('brew --prefix python@3.11').toString().trim();
          process.env.PYTHON_PATH = `${brewPython}/bin/python3`;
          console.log('✅ Installed Python 3.11 with brew');
          return true;
        } catch {
          console.log('❌ Failed to install Python with brew');
        }
      }
      
      return false;
    }
  } catch {
    console.log('❌ Python 3.10+ not found');
    console.log('   Please install Python from https://python.org');
    return false;
  }
}

async function checkDocker() {
  try {
    execSync('docker info', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

async function checkQdrant() {
  console.log('\n🐳 Checking Qdrant...');
  try {
    const response = await fetch('http://localhost:6333');
    const data = await response.json();
    if (data.title && data.title.includes('qdrant')) {
      console.log('✅ Qdrant is already running');
      return true;
    }
  } catch {}
  
  console.log('❌ Qdrant not found');
  
  // Check if Docker is available and running
  const dockerAvailable = await checkDocker();
  if (!dockerAvailable) {
    console.log('❌ Docker is not running or not installed');
    console.log('   Please install Docker from https://docker.com and ensure the Docker daemon is running');
    console.log('   Then run this setup again');
    return false;
  }
  
  // In non-interactive mode, skip standalone Qdrant - docker-compose will handle it
  let start = 'n';
  if (isInteractive) {
    start = await question('Would you like to start Qdrant with Docker? (y/n): ');
  } else {
    console.log('🤖 Non-interactive mode detected. Qdrant will be started with Docker Compose later...');
    return 'pending'; // Special value to indicate we'll handle it later
  }
  
  if (start.toLowerCase() === 'y') {
    try {
      // Check if a container named 'qdrant' already exists
      try {
        execSync('docker container inspect qdrant', { stdio: 'ignore' });
        console.log('Removing existing Qdrant container...');
        execSync('docker rm -f qdrant', { stdio: 'ignore' });
      } catch {
        // Container doesn't exist, which is fine
      }
      
      console.log('Starting Qdrant...');
      execSync('docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:latest', { stdio: 'inherit' });
      
      // Wait for Qdrant to be ready
      console.log('Waiting for Qdrant to start...');
      await new Promise(resolve => setTimeout(resolve, 3000)); // Initial wait for container to start
      
      let retries = 60; // Increase to 60 seconds
      while (retries > 0) {
        try {
          const response = await fetch('http://localhost:6333');
          const data = await response.json();
          if (data.title && data.title.includes('qdrant')) {
            console.log('✅ Qdrant started successfully');
            return true;
          }
        } catch (e) {
          // Show progress every 10 attempts
          if (retries % 10 === 0) {
            console.log(`   Still waiting... (${retries} seconds left)`);
            // Check if container is still running
            try {
              execSync('docker ps | grep qdrant', { stdio: 'pipe' });
            } catch {
              console.log('❌ Qdrant container stopped unexpectedly');
              return false;
            }
          }
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
        retries--;
      }
      
      console.log('❌ Qdrant failed to start properly');
      return false;
    } catch (error) {
      console.log('❌ Failed to start Qdrant:', error.message);
      return false;
    }
  }
  
  return false;
}

async function setupPythonEnvironment() {
  console.log('\n🐍 Setting up Python MCP server...');
  
  const mcpPath = join(projectRoot, 'mcp-server');
  const scriptsPath = join(projectRoot, 'scripts');
  
  try {
    // Check if venv already exists
    const venvPath = join(mcpPath, 'venv');
    let venvExists = false;
    try {
      await fs.access(venvPath);
      venvExists = true;
      console.log('✅ Virtual environment already exists');
    } catch {
      // venv doesn't exist, create it
    }
    
    if (!venvExists) {
      // Create virtual environment
      console.log('Creating virtual environment...');
      const pythonCmd = process.env.PYTHON_PATH || 'python3';
      try {
        execSync(`cd "${mcpPath}" && ${pythonCmd} -m venv venv`, { stdio: 'inherit' });
      } catch (venvError) {
        console.log('⚠️  Failed to create venv with python3, trying python...');
        try {
          execSync(`cd "${mcpPath}" && python -m venv venv`, { stdio: 'inherit' });
        } catch {
          console.log('❌ Failed to create virtual environment');
          console.log('📚 Fix: Install python3-venv package');
          console.log('   Ubuntu/Debian: sudo apt install python3-venv');
          console.log('   macOS: Should be included with Python');
          return false;
        }
      }
    }
    
    // Activate and upgrade pip first to avoid SSL issues
    console.log('Setting up pip in virtual environment...');
    const activateCmd = process.platform === 'win32' 
      ? 'venv\\Scripts\\activate' 
      : 'source venv/bin/activate';
    
    // First, try to install certifi to help with SSL issues
    console.log('Installing certificate handler...');
    try {
      execSync(`cd "${mcpPath}" && ${activateCmd} && pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org certifi`, { 
        stdio: 'pipe',
        shell: true 
      });
    } catch {
      // Continue even if certifi fails
    }
    
    // Upgrade pip and install wheel first
    try {
      // Use --no-cache-dir and --timeout to fail faster
      execSync(`cd "${mcpPath}" && ${activateCmd} && python -m pip install --no-cache-dir --timeout 5 --retries 1 --upgrade pip wheel setuptools`, { 
        stdio: 'pipe',
        shell: true 
      });
      console.log('✅ Pip upgraded successfully');
    } catch {
      // If upgrade fails due to SSL, skip it and continue
      console.log('⚠️  Pip upgrade failed (likely SSL issue), continuing with existing pip...');
    }
    
    // Now install dependencies
    console.log('Installing MCP server dependencies...');
    try {
      execSync(`cd "${mcpPath}" && ${activateCmd} && pip install --no-cache-dir --timeout 10 --retries 1 -e .`, { 
        stdio: 'pipe',
        shell: true 
      });
      console.log('✅ MCP server dependencies installed');
    } catch (error) {
      // Check for SSL errors
      const errorStr = error.toString();
      if (errorStr.includes('SSL') || errorStr.includes('HTTPS') || errorStr.includes('ssl')) {
        console.log('⚠️  SSL error detected. Attempting automatic fix...');
        
        // Try different approaches to fix SSL
        const fixes = [
          {
            name: 'Using trusted host flags',
            cmd: `${activateCmd} && pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --no-cache-dir -e .`
          },
          {
            name: 'Using index-url without SSL',
            cmd: `${activateCmd} && pip config set global.index-url https://pypi.org/simple/ && pip config set global.trusted-host "pypi.org files.pythonhosted.org" && pip install --no-cache-dir -e .`
          },
          {
            name: 'Using system certificates',
            cmd: `${activateCmd} && export SSL_CERT_FILE=$(python -m certifi) && pip install --no-cache-dir -e .`
          }
        ];
        
        for (const fix of fixes) {
          console.log(`\n   Trying: ${fix.name}...`);
          try {
            execSync(`cd "${mcpPath}" && ${fix.cmd}`, { 
              stdio: 'pipe',
              shell: true,
              env: { ...process.env, PYTHONWARNINGS: 'ignore:Unverified HTTPS request' }
            });
            console.log('   ✅ Success! Dependencies installed using workaround');
            return true;
          } catch (e) {
            console.log('   ❌ Failed');
          }
        }
        
        console.log('\n❌ All automatic fixes failed');
        return false;
      } else {
        console.log('❌ Failed to install dependencies');
        return false;
      }
    }
    
    // Install script dependencies
    console.log('Installing import script dependencies...');
    try {
      execSync(`cd "${mcpPath}" && ${activateCmd} && pip install -r "${scriptsPath}/requirements.txt"`, { 
        stdio: 'inherit',
        shell: true 
      });
    } catch (error) {
      // Try with trusted host if SSL error
      try {
        execSync(`cd "${mcpPath}" && ${activateCmd} && pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r "${scriptsPath}/requirements.txt"`, { 
          stdio: 'inherit',
          shell: true 
        });
      } catch {
        console.log('⚠️  Could not install script dependencies automatically');
        console.log('   You may need to install them manually later');
      }
    }
    
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
  let hasValidApiKey = false;
  
  try {
    envContent = await fs.readFile(envPath, 'utf-8');
  } catch {
    // .env doesn't exist, create it
  }
  
  // Check if we have a command line API key
  if (voyageKey) {
    if (voyageKey.startsWith('pa-')) {
      console.log('✅ Using API key from command line');
      envContent = envContent.replace(/VOYAGE_KEY=.*/g, '');
      envContent += `\nVOYAGE_KEY=${voyageKey}\n`;
      hasValidApiKey = true;
    } else {
      console.log('❌ Invalid API key format. Voyage keys start with "pa-"');
      process.exit(1);
    }
  } else if (localMode) {
    console.log('🏠 Running in local mode - API key not required');
    console.log('   Note: Semantic search will be disabled');
    hasValidApiKey = false; // Mark as false but don't fail
  } else {
    // Check if we already have a valid API key
    const existingKeyMatch = envContent.match(/VOYAGE_KEY=([^\s]+)/);
    if (existingKeyMatch && existingKeyMatch[1] && !existingKeyMatch[1].includes('your-')) {
      console.log('✅ Found existing Voyage API key in .env file');
      hasValidApiKey = true;
    } else {
      // Need to get API key
      console.log('\n🔑 Voyage AI API Key Setup');
      console.log('━━━━━━━━━━━━━━━━━━━━━━━━━');
      console.log('Claude Self-Reflect uses Voyage AI for semantic search.');
      console.log('You\'ll need a free API key to continue.\n');
      console.log('📝 Steps to get your API key:');
      console.log('   1. Visit https://www.voyageai.com/');
      console.log('   2. Click "Sign Up" (free account)');
      console.log('   3. Go to API Keys section');
      console.log('   4. Create a new API key');
      console.log('   5. Copy the key (starts with "pa-")\n');
      
      if (isInteractive) {
        const inputKey = await question('Paste your Voyage AI key here (or press Enter to skip): ');
        
        if (inputKey && inputKey.trim() && inputKey !== 'n') {
          // Validate key format
          if (inputKey.trim().startsWith('pa-')) {
            envContent = envContent.replace(/VOYAGE_KEY=.*/g, '');
            envContent += `\nVOYAGE_KEY=${inputKey.trim()}\n`;
            hasValidApiKey = true;
            console.log('✅ API key saved to .env file');
          } else {
            console.log('⚠️  Invalid key format. Voyage keys start with "pa-"');
            console.log('   You can add it manually to .env file later');
          }
        } else {
          console.log('\n⚠️  No API key provided');
          console.log('   Setup will continue, but you\'ll need to add it to .env file:');
          console.log('   VOYAGE_KEY=your-api-key-here');
        }
      } else {
        console.log('\n⚠️  Non-interactive mode: Cannot prompt for API key');
        console.log('   Please add your Voyage API key to the .env file:');
        console.log('   VOYAGE_KEY=your-api-key-here');
        
        // Create placeholder
        if (!envContent.includes('VOYAGE_KEY=')) {
          envContent += '\n# Get your free API key at https://www.voyageai.com/\nVOYAGE_KEY=your-voyage-api-key-here\n';
        }
      }
    }
  }
  
  // Set default Qdrant URL if not present
  if (!envContent.includes('QDRANT_URL=')) {
    envContent += 'QDRANT_URL=http://localhost:6333\n';
  }
  
  // Add other default settings if not present
  if (!envContent.includes('ENABLE_MEMORY_DECAY=')) {
    envContent += 'ENABLE_MEMORY_DECAY=false\n';
  }
  if (!envContent.includes('DECAY_WEIGHT=')) {
    envContent += 'DECAY_WEIGHT=0.3\n';
  }
  if (!envContent.includes('DECAY_SCALE_DAYS=')) {
    envContent += 'DECAY_SCALE_DAYS=90\n';
  }
  
  await fs.writeFile(envPath, envContent.trim() + '\n');
  console.log('✅ Environment file created/updated');
  
  return { apiKey: hasValidApiKey };
}

async function setupClaude() {
  console.log('\n🤖 Claude Code MCP Configuration...');
  
  const runScript = join(projectRoot, 'mcp-server', 'run-mcp.sh');
  
  // Check if Claude CLI is available
  try {
    execSync('which claude', { stdio: 'ignore' });
    
    // Try to add the MCP automatically
    try {
      const voyageKeyValue = voyageKey || process.env.VOYAGE_KEY || '';
      if (!voyageKeyValue && !localMode) {
        console.log('⚠️  No Voyage API key available for MCP configuration');
        console.log('\nAdd this to your Claude Code settings manually:');
        console.log('```bash');
        console.log(`claude mcp add claude-self-reflect "${runScript}" -e VOYAGE_KEY="<your-key>" -e QDRANT_URL="http://localhost:6333"`);
        console.log('```');
        return;
      }
      
      console.log('🔧 Adding MCP to Claude Code...');
      const mcpCommand = localMode 
        ? `claude mcp add claude-self-reflect "${runScript}" -e QDRANT_URL="http://localhost:6333"`
        : `claude mcp add claude-self-reflect "${runScript}" -e VOYAGE_KEY="${voyageKeyValue}" -e QDRANT_URL="http://localhost:6333"`;
      
      execSync(mcpCommand, { stdio: 'inherit' });
      console.log('✅ MCP added successfully!');
      console.log('\n⚠️  You may need to restart Claude Code for the changes to take effect.');
      
      // Store that we've configured MCP
      mcpConfigured = true;
    } catch (error) {
      console.log('⚠️  Could not add MCP automatically');
      console.log('\nAdd this to your Claude Code settings manually:');
      console.log('```bash');
      console.log(`claude mcp add claude-self-reflect "${runScript}" -e VOYAGE_KEY="${voyageKey || '<your-key>'}" -e QDRANT_URL="http://localhost:6333"`);
      console.log('```');
    }
  } catch {
    // Claude CLI not installed
    console.log('⚠️  Claude CLI not found. Please install Claude Code first.');
    console.log('\nOnce installed, add this MCP:');
    console.log('```bash');
    console.log(`claude mcp add claude-self-reflect "${runScript}" -e VOYAGE_KEY="${voyageKey || '<your-key>'}" -e QDRANT_URL="http://localhost:6333"`);
    console.log('```');
  }
  
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

async function showPreSetupInstructions() {
  console.log('🚀 Welcome to Claude Self-Reflect Setup!\n');
  console.log('This wizard will help you set up conversation memory for Claude.\n');
  
  console.log('📋 Before we begin, you\'ll need:');
  console.log('   1. Docker Desktop installed and running');
  console.log('   2. Python 3.10 or higher');
  console.log('   3. A Voyage AI API key (we\'ll help you get one)\n');
  
  if (isInteractive) {
    await question('Press Enter to continue...');
  }
}

async function importConversations() {
  console.log('\n📚 Import Claude Conversations...');
  
  // Skip import in local mode
  if (localMode) {
    console.log('🏠 Skipping import in local mode (no API key for embeddings)');
    return;
  }
  
  // Check if Claude logs directory exists
  const logsDir = join(process.env.HOME || process.env.USERPROFILE, '.claude', 'projects');
  let hasConversations = false;
  let totalProjects = 0;
  
  try {
    await fs.access(logsDir);
    const projects = await fs.readdir(logsDir);
    const validProjects = projects.filter(p => !p.startsWith('.'));
    totalProjects = validProjects.length;
    if (totalProjects > 0) {
      hasConversations = true;
      console.log(`✅ Found ${totalProjects} Claude projects`);
    }
  } catch {
    console.log('📭 No Claude conversations found yet');
    console.log('   Conversations will be imported automatically once you start using Claude Code');
    return;
  }
  
  if (!hasConversations) {
    console.log('📭 No Claude conversations found yet');
    console.log('   Conversations will be imported automatically once you start using Claude Code');
    return;
  }
  
  // Check if already imported or partially imported
  const stateFile = join(process.env.HOME || process.env.USERPROFILE, '.claude-self-reflect', 'imported-files.json');
  let importedProjects = 0;
  try {
    const stateData = await fs.readFile(stateFile, 'utf-8');
    const state = JSON.parse(stateData);
    if (state.projects && Object.keys(state.projects).length > 0) {
      importedProjects = Object.keys(state.projects).length;
      
      // Check if all projects are imported
      if (importedProjects >= totalProjects) {
        console.log('✅ All conversations already imported');
        console.log(`   ${importedProjects} projects in database`);
        return;
      } else {
        console.log(`📊 Partially imported: ${importedProjects}/${totalProjects} projects`);
        console.log('   Continuing import for remaining projects...');
      }
    }
  } catch {
    // State file doesn't exist, proceed with import
  }
  
  // Run import
  console.log('\n🔄 Importing conversations...');
  console.log('   This may take a few minutes depending on your conversation history');
  
  try {
    const pythonCmd = process.env.PYTHON_PATH || 'python3';
    const importScript = join(projectRoot, 'scripts', 'import-conversations-voyage.py');
    
    // Use the venv Python directly - platform specific
    let venvPython;
    if (process.platform === 'win32') {
      venvPython = join(projectRoot, 'mcp-server', 'venv', 'Scripts', 'python.exe');
    } else if (process.platform === 'darwin') {
      // macOS
      venvPython = join(projectRoot, 'mcp-server', 'venv', 'bin', 'python');
    } else {
      // Linux
      venvPython = join(projectRoot, 'mcp-server', 'venv', 'bin', 'python');
    }
    
    // Verify venv Python exists
    try {
      await fs.access(venvPython);
    } catch {
      console.log('⚠️  Virtual environment Python not found');
      console.log('   Please run the import manually:');
      console.log('   cd claude-self-reflect');
      console.log('   source mcp-server/venv/bin/activate');
      console.log('   python scripts/import-conversations-voyage.py');
      return;
    }
      
    const importProcess = spawn(venvPython, [importScript], {
      cwd: projectRoot,
      env: {
        ...process.env,
        VOYAGE_KEY: voyageKey || process.env.VOYAGE_KEY,
        QDRANT_URL: 'http://localhost:6333',
        LOGS_DIR: logsDir,
        STATE_FILE: stateFile
      },
      stdio: 'inherit'
    });
    
    await new Promise((resolve, reject) => {
      importProcess.on('exit', (code) => {
        if (code === 0) {
          console.log('\n✅ Conversations imported successfully!');
          resolve();
        } else {
          console.log('\n⚠️  Import completed with warnings');
          console.log('   Some conversations may not have been imported');
          console.log('   You can run the import again later if needed');
          resolve(); // Don't fail setup if import has issues
        }
      });
      
      importProcess.on('error', (err) => {
        console.log('\n⚠️  Could not run import automatically');
        console.log('   You can import manually later');
        resolve(); // Don't fail setup
      });
    });
    
  } catch (error) {
    console.log('\n⚠️  Could not run import automatically:', error.message);
    console.log('   You can import conversations manually later');
  }
}

async function showSystemDashboard() {
  console.log('\n📊 System Health Dashboard');
  console.log('═══════════════════════════════════════════════════════════════\n');
  
  // Check system components
  const status = {
    docker: false,
    qdrant: false,
    python: false,
    venv: false,
    apiKey: false,
    imported: 0,
    total: 0,
    watcherInstalled: false,
    watcherRunning: false
  };
  
  // Docker status
  try {
    execSync('docker info', { stdio: 'ignore' });
    status.docker = true;
  } catch {}
  
  // Qdrant status
  try {
    const response = await fetch('http://localhost:6333');
    const data = await response.json();
    if (data.title && data.title.includes('qdrant')) {
      status.qdrant = true;
    }
  } catch {}
  
  // Python status
  try {
    const pythonCmd = process.env.PYTHON_PATH || 'python3';
    execSync(`${pythonCmd} --version`, { stdio: 'ignore' });
    status.python = true;
  } catch {}
  
  // Virtual environment status
  const venvPath = join(projectRoot, 'mcp-server', 'venv');
  try {
    await fs.access(venvPath);
    status.venv = true;
  } catch {}
  
  // API key status
  const envPath = join(projectRoot, '.env');
  try {
    const envContent = await fs.readFile(envPath, 'utf-8');
    const keyMatch = envContent.match(/VOYAGE_KEY=([^\s]+)/);
    if (keyMatch && keyMatch[1] && !keyMatch[1].includes('your-')) {
      status.apiKey = true;
    }
  } catch {}
  
  // Import status
  const logsDir = join(process.env.HOME || process.env.USERPROFILE, '.claude', 'projects');
  try {
    const projects = await fs.readdir(logsDir);
    status.total = projects.filter(p => !p.startsWith('.')).length;
  } catch {}
  
  const stateFile = join(process.env.HOME || process.env.USERPROFILE, '.claude-self-reflect', 'imported-files.json');
  try {
    const stateData = await fs.readFile(stateFile, 'utf-8');
    const state = JSON.parse(stateData);
    if (state.projects) {
      status.imported = Object.keys(state.projects).length;
    }
  } catch {}
  
  // Watcher status
  try {
    // Check if watcher script exists
    const watcherScript = join(projectRoot, 'scripts', 'import-watcher.py');
    await fs.access(watcherScript);
    status.watcherInstalled = true;
    
    // Check if watcher is running via Docker
    try {
      const dockerStatus = execSync('docker ps --filter "name=claude-reflection-watcher" --format "{{.Names}}" 2>/dev/null', {
        cwd: projectRoot,
        encoding: 'utf-8'
      }).toString().trim();
      
      if (dockerStatus.includes('watcher')) {
        status.watcherRunning = true;
      }
    } catch {
      // Docker compose not available or watcher not running
    }
  } catch {
    status.watcherInstalled = false;
  }
  
  // Display dashboard
  console.log('🔧 System Components:');
  console.log(`   Docker:        ${status.docker ? '✅ Running' : '❌ Not running'}`);
  console.log(`   Qdrant:        ${status.qdrant ? '✅ Running on port 6333' : '❌ Not accessible'}`);
  console.log(`   Python:        ${status.python ? '✅ Installed' : '❌ Not found'}`);
  console.log(`   Virtual Env:   ${status.venv ? '✅ Created' : '❌ Not created'}`);
  console.log(`   API Key:       ${status.apiKey ? '✅ Configured' : localMode ? '🏠 Local mode' : '❌ Not configured'}`);
  
  console.log('\n📚 Import Status:');
  if (status.total === 0) {
    console.log('   No Claude conversations found yet');
  } else if (status.imported === 0) {
    console.log(`   📭 Not started (${status.total} projects available)`);
  } else if (status.imported < status.total) {
    const percent = Math.round((status.imported / status.total) * 100);
    console.log(`   🔄 In progress: ${status.imported}/${status.total} projects (${percent}%)`);
    console.log(`   ▓${'▓'.repeat(Math.floor(percent/5))}${'░'.repeat(20-Math.floor(percent/5))} ${percent}%`);
  } else {
    console.log(`   ✅ Complete: ${status.imported} projects imported`);
  }
  
  console.log('\n🔄 Continuous Import (Watcher):');
  if (status.watcherInstalled) {
    console.log('   Status: ✅ Available (run manually or with Docker Compose)');
    console.log('   • Manual: python scripts/import-watcher.py');
    console.log('   • Docker: docker compose --profile watch up -d');
  } else {
    console.log('   Status: ❌ Not available');
  }
  
  // Check for issues
  const issues = [];
  if (!status.docker) issues.push('Docker is not running');
  if (!status.qdrant && status.docker) issues.push('Qdrant is not running');
  if (!status.python) issues.push('Python is not installed');
  if (!status.apiKey && !localMode) issues.push('Voyage API key not configured');
  
  if (issues.length > 0) {
    console.log('\n⚠️  Issues Found:');
    issues.forEach(issue => console.log(`   • ${issue}`));
    console.log('\n💡 Run setup again to fix these issues');
  } else if (status.imported < status.total) {
    console.log('\n💡 Setup will continue with import process...');
  } else {
    console.log('\n✅ System is fully configured and healthy!');
  }
  
  console.log('\n═══════════════════════════════════════════════════════════════\n');
  
  return {
    healthy: issues.length === 0,
    needsImport: status.imported < status.total,
    issues
  };
}

async function setupWatcher() {
  console.log('\n⚙️  Setting up Continuous Import (Watcher)...');
  
  const watcherScript = join(projectRoot, 'scripts', 'import-watcher.py');
  
  // Check if watcher exists
  try {
    await fs.access(watcherScript);
    console.log('✅ Watcher script found');
    
    // Skip in local mode
    if (localMode) {
      console.log('🏠 Skipping watcher in local mode');
      return;
    }
    
    // Ask if user wants to enable watcher
    let enableWatcher = 'y';
    if (isInteractive) {
      console.log('\n💡 The watcher monitors for new conversations and imports them automatically.');
      enableWatcher = await question('Enable continuous import watcher? (y/n): ');
    }
    
    if (enableWatcher.toLowerCase() === 'y') {
      // Check if docker-compose.yaml exists
      const dockerComposeFile = join(projectRoot, 'docker-compose.yaml');
      try {
        await fs.access(dockerComposeFile);
        
        console.log('\n🐳 Starting watcher with Docker Compose...');
        try {
          // First ensure .env has VOYAGE_KEY to avoid warnings
          const envPath = join(projectRoot, '.env');
          const envContent = await fs.readFile(envPath, 'utf-8');
          if (!envContent.includes('VOYAGE_KEY=') && voyageKey) {
            await fs.appendFile(envPath, `\nVOYAGE_KEY=${voyageKey}\n`);
          }
          
          // Clean up all existing containers first
          console.log('🧹 Cleaning up existing containers...');
          try {
            // Stop all claude-reflection containers
            execSync('docker compose down 2>/dev/null || true', { 
              cwd: projectRoot,
              stdio: 'pipe' 
            });
            
            // Also stop any standalone containers
            execSync('docker stop claude-reflection-watcher claude-reflection-qdrant qdrant 2>/dev/null || true', { 
              stdio: 'pipe' 
            });
            
            // Remove them
            execSync('docker rm claude-reflection-watcher claude-reflection-qdrant qdrant 2>/dev/null || true', { 
              stdio: 'pipe' 
            });
            
            // Wait a moment for cleanup
            await new Promise(resolve => setTimeout(resolve, 2000));
          } catch {}
          
          // Start both services with compose
          console.log('🚀 Starting Qdrant and Watcher services...');
          execSync('docker compose --profile watch up -d', { 
            cwd: projectRoot,
            stdio: 'pipe' // Use pipe to capture output 
          });
          
          console.log('⏳ Waiting for containers to start...');
          await new Promise(resolve => setTimeout(resolve, 8000)); // Give more time
          
          // Check container status
          try {
            const psOutput = execSync('docker ps --filter "name=claude-reflection" --format "table {{.Names}}\t{{.Status}}"', {
              cwd: projectRoot,
              encoding: 'utf8'
            });
            
            const qdrantReady = psOutput.includes('claude-reflection-qdrant') && psOutput.includes('Up');
            const watcherReady = psOutput.includes('claude-reflection-watcher') && psOutput.includes('Up');
            
            if (qdrantReady && watcherReady) {
              console.log('✅ All services started successfully!');
              console.log('   • Qdrant is ready for storing conversations');
              console.log('   • Watcher will check for new conversations every 60 seconds');
              console.log('\n📊 Container Status:');
              console.log(psOutput);
              console.log('\n📝 Useful commands:');
              console.log('   Check status: docker compose ps');
              console.log('   View logs: docker compose logs -f watcher');
              console.log('   Stop services: docker compose --profile watch down');
            } else if (qdrantReady) {
              console.log('✅ Qdrant started successfully');
              console.log('⏳ Watcher is still starting...');
              console.log('\n📝 Check full status with:');
              console.log('   docker compose ps');
              console.log('   docker compose logs watcher');
            } else {
              console.log('⏳ Services are still starting...');
              console.log('\n📝 Check status with:');
              console.log('   docker compose ps');
              console.log('   docker compose logs');
            }
          } catch (statusError) {
            console.log('✅ Services deployment initiated');
            console.log('\n📝 Check status with:');
            console.log('   docker compose ps');
          }
        } catch (error) {
          console.log('⚠️  Could not start watcher automatically');
          console.log('Error:', error.message);
          console.log('\n📝 To start manually, run:');
          console.log('   cd claude-self-reflect');
          console.log('   docker compose --profile watch up -d');
        }
      } catch {
        // Fallback to manual Python execution
        console.log('\n📝 To enable the watcher, run:');
        console.log('   cd claude-self-reflect');
        console.log('   source mcp-server/venv/bin/activate');
        console.log('   python scripts/import-watcher.py &');
      }
    } else {
      console.log('\n📝 You can enable the watcher later by running:');
      console.log('   docker compose --profile watch up -d');
    }
  } catch {
    console.log('⚠️  Watcher script not found');
  }
}

async function verifyMCP() {
  console.log('\n🔍 Verifying MCP Installation...');
  
  // Skip verification if MCP wasn't configured
  if (!mcpConfigured) {
    console.log('⚠️  MCP was not automatically configured. Please add it manually and verify.');
    return;
  }
  
  try {
    // Check if MCP is listed
    const mcpList = execSync('claude mcp list', { encoding: 'utf8' });
    if (!mcpList.includes('claude-self-reflect')) {
      console.log('❌ MCP not found in Claude Code');
      return;
    }
    
    console.log('✅ MCP is installed in Claude Code');
    
    // Create a test verification script
    const testScript = `#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-server', 'src'))

from mcp_server_qdrant.server import reflect_on_past, store_reflection

# Test storing a reflection
try:
    result = store_reflection(
        insight="Claude Self-Reflect setup completed successfully!",
        tags=["setup", "test", "verification"],
        importance="high"
    )
    print("✅ Store reflection: Success")
except Exception as e:
    print(f"❌ Store reflection failed: {e}")
    sys.exit(1)

# Test searching
try:
    results = reflect_on_past("setup test verification")
    if results and len(results) > 0:
        print("✅ Search reflection: Success")
        print(f"   Found {len(results)} results")
    else:
        print("⚠️  Search returned no results (this is normal for first setup)")
except Exception as e:
    print(f"❌ Search reflection failed: {e}")
    sys.exit(1)
`;
    
    // Write test script
    const testPath = join(projectRoot, 'test-mcp.py');
    await fs.writeFile(testPath, testScript, { mode: 0o755 });
    
    // Run the test
    console.log('\n🧪 Testing MCP functionality...');
    try {
      const testResult = execSync(`cd "${projectRoot}" && source mcp-server/venv/bin/activate && python test-mcp.py`, {
        encoding: 'utf8',
        shell: '/bin/bash'
      });
      console.log(testResult);
      
      // Clean up test script
      await fs.unlink(testPath);
      
      console.log('\n✅ MCP verification complete! The reflection tools are working.');
    } catch (error) {
      console.log('❌ MCP test failed:', error.message);
      console.log('\n⚠️  The MCP may need to be restarted in Claude Code.');
      
      // Clean up test script
      try { await fs.unlink(testPath); } catch {}
    }
    
  } catch (error) {
    console.log('⚠️  Could not verify MCP:', error.message);
    console.log('\nPlease verify manually by:');
    console.log('1. Restarting Claude Code');
    console.log('2. Checking that the reflection tools appear in Claude');
  }
}

async function main() {
  // Show dashboard first if system is partially configured
  const venvExists = await fs.access(join(projectRoot, 'mcp-server', 'venv')).then(() => true).catch(() => false);
  const envExists = await fs.access(join(projectRoot, '.env')).then(() => true).catch(() => false);
  
  if (venvExists || envExists) {
    // System has been partially configured, show dashboard
    const dashboardStatus = await showSystemDashboard();
    
    if (dashboardStatus.healthy && !dashboardStatus.needsImport) {
      // Everything is already set up
      if (isInteractive) {
        const proceed = await question('System is already configured. Continue with setup anyway? (y/n): ');
        if (proceed.toLowerCase() !== 'y') {
          console.log('\n👋 Setup cancelled. Your system is already configured!');
          if (rl) rl.close();
          process.exit(0);
        }
      }
    }
  }
  
  // Check for non-interactive mode without required flags
  if (!isInteractive && !voyageKey && !localMode) {
    console.log('❌ Non-interactive mode requires either --voyage-key or --local flag\n');
    console.log('Usage:');
    console.log('  claude-self-reflect setup --voyage-key=<your-key>');
    console.log('  claude-self-reflect setup --local\n');
    console.log('Get your free API key at: https://www.voyageai.com/');
    process.exit(1);
  }
  
  await showPreSetupInstructions();
  
  // Check prerequisites
  const pythonOk = await checkPython();
  if (!pythonOk) {
    console.log('\n❌ Setup cannot continue without Python');
    console.log('\n📋 Fix Required:');
    console.log('   1. Install Python 3.10+ from https://python.org');
    console.log('   2. Ensure python3 is in your PATH');
    console.log('\n🔄 After fixing, run again:');
    console.log('   claude-self-reflect setup');
    process.exit(1);
  }
  
  // Check Docker and Qdrant
  const qdrantOk = await checkQdrant();
  if (qdrantOk === false) {
    console.log('\n❌ Setup cannot continue without Qdrant');
    console.log('\n📋 Fix Required - Choose one:');
    console.log('\n   Option 1: Start Docker Desktop');
    console.log('   - Open Docker Desktop application');
    console.log('   - Wait for it to fully start (green icon)');
    console.log('\n   Option 2: Manually start Qdrant');
    console.log('   - docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest');
    console.log('\n🔄 After fixing, run again:');
    console.log('   claude-self-reflect setup');
    
    if (rl) rl.close();
    process.exit(1);
  }
  // If qdrantOk is 'pending', we'll start it with docker-compose later
  
  // Setup Python environment
  const pythonEnvOk = await setupPythonEnvironment();
  if (!pythonEnvOk) {
    console.log('\n❌ Python environment setup failed');
    console.log('\n📋 Fix Required:');
    console.log('\n   For SSL/HTTPS errors:');
    console.log('   - macOS: brew reinstall python@3.10');
    console.log('   - Ubuntu: sudo apt-get install python3-dev libssl-dev');
    console.log('   - Or use a different Python installation');
    console.log('\n   For venv errors:');
    console.log('   - Ubuntu: sudo apt install python3-venv');
    console.log('   - macOS: Should be included with Python');
    console.log('\n🔄 After fixing, run again:');
    console.log('   claude-self-reflect setup');
    
    if (rl) rl.close();
    process.exit(1);
  }
  
  // Configure environment
  const envOk = await configureEnvironment();
  if (!localMode && (!envOk || !envOk.apiKey)) {
    console.log('\n⚠️  No Voyage API key configured');
    console.log('\n📋 Next Steps:');
    console.log('   1. Get your free API key from https://www.voyageai.com/');
    console.log('   2. Add it to the .env file:');
    console.log('      VOYAGE_KEY=your-api-key-here');
    console.log('\n🔄 After adding the key, run again:');
    console.log('   claude-self-reflect setup');
    console.log('\n💡 Or run in local mode:');
    console.log('   claude-self-reflect setup --local');
    
    if (rl) rl.close();
    process.exit(1);
  }
  
  // Install agents
  await installAgents();
  
  // Show Claude configuration
  await setupClaude();
  
  // Import conversations
  await importConversations();
  
  // Setup watcher for continuous import
  await setupWatcher();
  
  // Verify MCP installation
  await verifyMCP();
  
  console.log('\n✅ Setup complete!');
  console.log('\nNext steps:');
  if (!mcpConfigured) {
    console.log('1. Add the MCP to Claude Code manually (see instructions above)');
    console.log('2. Restart Claude Code');
    console.log('3. Start using the reflection tools!');
  } else {
    console.log('1. Restart Claude Code if needed');
    console.log('2. Start using the reflection tools!');
    console.log('   - Ask about past conversations');
    console.log('   - Store important insights');
  }
  console.log('\nFor more info: https://github.com/ramakay/claude-self-reflect');
  
  if (rl) rl.close();
  process.exit(0);
}

main().catch(console.error);