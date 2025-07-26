#!/usr/bin/env node
import readline from 'readline';
import { execSync, spawn } from 'child_process';
import { existsSync, mkdirSync, writeFileSync, readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { homedir } from 'os';
import https from 'https';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  red: '\x1b[31m',
  cyan: '\x1b[36m'
};

function question(prompt) {
  return new Promise((resolve) => {
    rl.question(prompt, resolve);
  });
}

function success(message) {
  console.log(`${colors.green}✅ ${message}${colors.reset}`);
}

function info(message) {
  console.log(`${colors.blue}ℹ️  ${message}${colors.reset}`);
}

function warning(message) {
  console.log(`${colors.yellow}⚠️  ${message}${colors.reset}`);
}

function error(message) {
  console.log(`${colors.red}❌ ${message}${colors.reset}`);
}

function header(message) {
  console.log(`\n${colors.cyan}${'='.repeat(60)}${colors.reset}`);
  console.log(`${colors.cyan}${message}${colors.reset}`);
  console.log(`${colors.cyan}${'='.repeat(60)}${colors.reset}\n`);
}

async function checkCommand(command) {
  try {
    execSync(`which ${command}`, { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

async function checkDocker() {
  if (!await checkCommand('docker')) {
    return { installed: false };
  }
  
  try {
    execSync('docker info', { stdio: 'ignore' });
    return { installed: true, running: true };
  } catch {
    return { installed: true, running: false };
  }
}

async function checkPython() {
  const commands = ['python3', 'python'];
  for (const cmd of commands) {
    if (await checkCommand(cmd)) {
      try {
        const version = execSync(`${cmd} --version`, { encoding: 'utf8' }).trim();
        return { installed: true, command: cmd, version };
      } catch {}
    }
  }
  return { installed: false };
}

async function validateApiKey(provider, apiKey) {
  return new Promise((resolve) => {
    if (!apiKey || apiKey.length < 10) {
      resolve(false);
      return;
    }

    let options;
    switch (provider) {
      case 'voyage':
        options = {
          hostname: 'api.voyageai.com',
          path: '/v1/models',
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${apiKey}`
          }
        };
        break;
      case 'openai':
        options = {
          hostname: 'api.openai.com',
          path: '/v1/models',
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${apiKey}`
          }
        };
        break;
      case 'gemini':
        // Gemini uses a different validation approach
        resolve(apiKey.startsWith('AI') && apiKey.length > 20);
        return;
      default:
        resolve(true);
        return;
    }

    const req = https.request(options, (res) => {
      resolve(res.statusCode === 200);
    });

    req.on('error', () => resolve(false));
    req.setTimeout(5000, () => {
      req.destroy();
      resolve(false);
    });
    req.end();
  });
}

async function setupQdrant() {
  header('Setting up Qdrant Vector Database');
  
  const docker = await checkDocker();
  
  if (!docker.installed) {
    error('Docker is not installed');
    console.log('\nTo install Docker:');
    console.log('1. Visit https://docs.docker.com/get-docker/');
    console.log('2. Download Docker Desktop for your platform');
    console.log('3. Run the installer and start Docker');
    console.log('4. Run this setup again\n');
    
    const proceed = await question('Would you like to continue without Docker? (y/n): ');
    if (proceed.toLowerCase() !== 'y') {
      return false;
    }
    
    warning('Continuing without vector database - search functionality will be limited');
    return true;
  }
  
  if (!docker.running) {
    error('Docker is installed but not running');
    console.log('Please start Docker Desktop and run this setup again\n');
    return false;
  }
  
  // Check if Qdrant is already running
  try {
    execSync('docker ps | grep qdrant', { stdio: 'ignore' });
    success('Qdrant is already running');
    return true;
  } catch {
    // Not running, let's start it
  }
  
  info('Starting Qdrant container...');
  try {
    execSync('docker run -d --name qdrant -p 6333:6333 --restart always qdrant/qdrant:latest', {
      stdio: 'inherit'
    });
    success('Qdrant started successfully');
    return true;
  } catch (err) {
    // Container might already exist but be stopped
    try {
      execSync('docker start qdrant', { stdio: 'inherit' });
      success('Qdrant restarted successfully');
      return true;
    } catch {
      error('Failed to start Qdrant');
      return false;
    }
  }
}

async function selectEmbeddingProvider() {
  header('Choose Your Embedding Provider');
  
  console.log('Embedding models convert your conversations into searchable vectors.\n');
  
  console.log(`${colors.green}1. Voyage AI (Recommended)${colors.reset}`);
  console.log('   ✅ 200M tokens FREE - covers most users completely');
  console.log('   ✅ Best quality for conversation search');
  console.log('   ✅ Only $0.02/1M tokens after free tier\n');
  
  console.log(`${colors.blue}2. Google Gemini${colors.reset}`);
  console.log('   ✅ Completely FREE (unlimited usage)');
  console.log('   ⚠️  Your data used to improve Google products');
  console.log('   ✅ Good multilingual support\n');
  
  console.log(`${colors.yellow}3. Local Processing${colors.reset}`);
  console.log('   ✅ Completely FREE, works offline');
  console.log('   ✅ No API keys, no data sharing');
  console.log('   ⚠️  Lower quality results, slower processing\n');
  
  console.log(`${colors.cyan}4. OpenAI${colors.reset}`);
  console.log('   ❌ No free tier');
  console.log('   ✅ $0.02/1M tokens (same as Voyage paid)');
  console.log('   ✅ Good quality, established ecosystem\n');
  
  const choice = await question('Enter your choice (1-4): ');
  
  switch (choice) {
    case '1': return 'voyage';
    case '2': return 'gemini';
    case '3': return 'local';
    case '4': return 'openai';
    default:
      warning('Invalid choice, defaulting to Voyage AI');
      return 'voyage';
  }
}

async function getApiKey(provider) {
  if (provider === 'local') return null;
  
  const urls = {
    voyage: 'https://dash.voyageai.com/',
    gemini: 'https://ai.google.dev/gemini-api/docs',
    openai: 'https://platform.openai.com/api-keys'
  };
  
  console.log(`\nTo get your API key, visit: ${colors.blue}${urls[provider]}${colors.reset}`);
  
  let apiKey;
  let valid = false;
  
  while (!valid) {
    apiKey = await question(`Enter your ${provider.toUpperCase()} API key: `);
    
    if (!apiKey) {
      const skip = await question('Skip API key for now? (y/n): ');
      if (skip.toLowerCase() === 'y') {
        return null;
      }
      continue;
    }
    
    info('Validating API key...');
    valid = await validateApiKey(provider, apiKey);
    
    if (valid) {
      success('API key validated successfully');
    } else {
      error('Invalid API key. Please check and try again.');
    }
  }
  
  return apiKey;
}

async function setupPython() {
  header('Setting up Python Dependencies');
  
  const python = await checkPython();
  
  if (!python.installed) {
    error('Python is not installed');
    console.log('\nTo install Python:');
    console.log('1. Visit https://www.python.org/downloads/');
    console.log('2. Download Python 3.8 or later');
    console.log('3. Run the installer\n');
    return false;
  }
  
  success(`Found ${python.version}`);
  
  // Clone the repository if needed
  const repoPath = join(homedir(), '.claude-self-reflect');
  
  if (!existsSync(repoPath)) {
    info('Downloading import scripts...');
    try {
      execSync(`git clone https://github.com/ramakay/claude-self-reflect.git "${repoPath}"`, {
        stdio: 'inherit'
      });
      success('Downloaded import scripts');
    } catch {
      error('Failed to download import scripts');
      return false;
    }
  }
  
  // Install Python dependencies
  info('Installing Python dependencies...');
  const requirementsPath = join(repoPath, 'scripts', 'requirements.txt');
  
  try {
    execSync(`${python.command} -m pip install -r "${requirementsPath}"`, {
      stdio: 'inherit',
      cwd: repoPath
    });
    success('Python dependencies installed');
    return { command: python.command, repoPath };
  } catch {
    error('Failed to install Python dependencies');
    warning('You may need to install pip or run with administrator privileges');
    return false;
  }
}

async function configureMemoryDecay() {
  header('Configure Memory Decay (Optional)');
  
  console.log('Memory Decay helps prioritize recent conversations over older ones.\n');
  console.log('When enabled, search results will favor more recent memories while');
  console.log('still including relevant older content.\n');
  
  const enable = await question('Enable memory decay? (y/n) [default: n]: ');
  
  if (enable.toLowerCase() === 'y') {
    console.log('\nDecay Configuration:');
    console.log('1. Light decay (30 days) - Minimal recency bias');
    console.log('2. Medium decay (90 days) - Balanced approach (Recommended)');
    console.log('3. Strong decay (180 days) - Strong recency preference');
    console.log('4. Custom configuration\n');
    
    const choice = await question('Choose decay configuration (1-4) [default: 2]: ') || '2';
    
    let weight = 0.3;
    let scaleDays = 90;
    
    switch (choice) {
      case '1':
        weight = 0.1;
        scaleDays = 30;
        break;
      case '2':
        weight = 0.3;
        scaleDays = 90;
        break;
      case '3':
        weight = 0.5;
        scaleDays = 180;
        break;
      case '4':
        const customWeight = await question('Decay weight (0.1-1.0) [default: 0.3]: ');
        const customScale = await question('Decay scale in days [default: 90]: ');
        weight = parseFloat(customWeight) || 0.3;
        scaleDays = parseInt(customScale) || 90;
        break;
    }
    
    success(`Memory decay configured: weight=${weight}, scale=${scaleDays} days`);
    return { enabled: true, weight, scaleDays };
  }
  
  return { enabled: false };
}

async function saveConfiguration(config) {
  const envPath = join(homedir(), '.claude-self-reflect', '.env');
  const envDir = dirname(envPath);
  
  if (!existsSync(envDir)) {
    mkdirSync(envDir, { recursive: true });
  }
  
  let envContent = '# Claude Self-Reflect Configuration\n';
  envContent += '# Generated by setup wizard\n\n';
  
  if (config.provider === 'voyage' && config.apiKey) {
    envContent += `VOYAGE_API_KEY="${config.apiKey}"\n`;
  } else if (config.provider === 'gemini' && config.apiKey) {
    envContent += `GEMINI_API_KEY="${config.apiKey}"\n`;
  } else if (config.provider === 'openai' && config.apiKey) {
    envContent += `OPENAI_API_KEY="${config.apiKey}"\n`;
  } else if (config.provider === 'local') {
    envContent += 'USE_LOCAL_EMBEDDINGS=true\n';
  }
  
  envContent += 'QDRANT_URL=http://localhost:6333\n';
  
  // Memory decay configuration
  envContent += '\n# Memory Decay Configuration\n';
  envContent += `ENABLE_MEMORY_DECAY=${config.memoryDecay?.enabled ? 'true' : 'false'}\n`;
  if (config.memoryDecay?.enabled) {
    envContent += `DECAY_WEIGHT=${config.memoryDecay.weight}\n`;
    envContent += `DECAY_SCALE_DAYS=${config.memoryDecay.scaleDays}\n`;
  }
  
  writeFileSync(envPath, envContent);
  success(`Configuration saved to ${envPath}`);
}

async function runImport(pythonConfig, provider, apiKey) {
  header('Importing Conversation History');
  
  const claudeLogsPath = join(homedir(), '.claude', 'projects');
  
  if (!existsSync(claudeLogsPath)) {
    warning('No Claude conversation logs found at ~/.claude/projects');
    console.log('Make sure you have used Claude Desktop and have some conversations');
    return;
  }
  
  info('Scanning for conversation files...');
  const scriptPath = join(pythonConfig.repoPath, 'scripts', 'import-openai-enhanced.py');
  
  // Set environment variables for the import
  const env = { ...process.env };
  if (provider === 'voyage' && apiKey) {
    env.VOYAGE_API_KEY = apiKey;
  } else if (provider === 'gemini' && apiKey) {
    env.GEMINI_API_KEY = apiKey;
  } else if (provider === 'openai' && apiKey) {
    env.OPENAI_API_KEY = apiKey;
  } else if (provider === 'local') {
    env.USE_LOCAL_EMBEDDINGS = 'true';
  }
  
  const importProcess = spawn(pythonConfig.command, [scriptPath], {
    cwd: pythonConfig.repoPath,
    env,
    stdio: 'inherit'
  });
  
  return new Promise((resolve) => {
    importProcess.on('close', (code) => {
      if (code === 0) {
        success('Import completed successfully');
        resolve(true);
      } else {
        error('Import failed');
        resolve(false);
      }
    });
  });
}

async function setupClaudeDesktop(memoryDecayConfig) {
  header('Configure Claude Desktop (Optional)');
  
  console.log('To use this with Claude Desktop, add the following to your config:\n');
  
  const env = {
    QDRANT_URL: 'http://localhost:6333'
  };
  
  // Add memory decay configuration if enabled
  if (memoryDecayConfig?.enabled) {
    env.ENABLE_MEMORY_DECAY = 'true';
    env.DECAY_WEIGHT = memoryDecayConfig.weight.toString();
    env.DECAY_SCALE_DAYS = memoryDecayConfig.scaleDays.toString();
  }
  
  const config = {
    mcpServers: {
      'claude-self-reflect': {
        command: 'npx',
        args: ['claude-self-reflect'],
        env
      }
    }
  };
  
  console.log(JSON.stringify(config, null, 2));
  
  console.log('\nConfig file location:');
  console.log('- macOS: ~/Library/Application Support/Claude/claude_desktop_config.json');
  console.log('- Windows: %APPDATA%\\Claude\\claude_desktop_config.json');
  console.log('- Linux: ~/.config/Claude/claude_desktop_config.json\n');
  
  const configure = await question('Would you like to automatically configure Claude Desktop? (y/n): ');
  
  if (configure.toLowerCase() === 'y') {
    // Detect platform and find config file
    const platform = process.platform;
    let configPath;
    
    if (platform === 'darwin') {
      configPath = join(homedir(), 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
    } else if (platform === 'win32') {
      configPath = join(process.env.APPDATA, 'Claude', 'claude_desktop_config.json');
    } else {
      configPath = join(homedir(), '.config', 'Claude', 'claude_desktop_config.json');
    }
    
    try {
      let existingConfig = {};
      if (existsSync(configPath)) {
        existingConfig = JSON.parse(readFileSync(configPath, 'utf8'));
      }
      
      // Merge configurations
      existingConfig.mcpServers = existingConfig.mcpServers || {};
      existingConfig.mcpServers['claude-self-reflect'] = config.mcpServers['claude-self-reflect'];
      
      // Ensure directory exists
      mkdirSync(dirname(configPath), { recursive: true });
      
      // Write config
      writeFileSync(configPath, JSON.stringify(existingConfig, null, 2));
      success('Claude Desktop configured successfully');
      info('Restart Claude Desktop to use the new configuration');
    } catch (err) {
      error('Failed to configure Claude Desktop automatically');
      console.log('Please add the configuration manually');
    }
  }
}

async function main() {
  console.clear();
  header('🚀 Claude Self-Reflect Setup Wizard');
  
  console.log('This wizard will help you set up Claude Self-Reflect in just a few minutes.\n');
  
  // Step 1: Check and setup Qdrant
  const qdrantOk = await setupQdrant();
  if (!qdrantOk) {
    error('Setup incomplete. Please fix the issues and try again.');
    rl.close();
    process.exit(1);
  }
  
  // Step 2: Select embedding provider
  const provider = await selectEmbeddingProvider();
  
  // Step 3: Get API key
  const apiKey = await getApiKey(provider);
  
  // Step 4: Setup Python
  const pythonConfig = await setupPython();
  if (!pythonConfig) {
    error('Setup incomplete. Please fix the issues and try again.');
    rl.close();
    process.exit(1);
  }
  
  // Step 5: Configure memory decay
  const memoryDecay = await configureMemoryDecay();
  
  // Step 6: Save configuration
  await saveConfiguration({ provider, apiKey, memoryDecay });
  
  // Step 7: Run import
  if (apiKey || provider === 'local') {
    const runImportNow = await question('\nWould you like to import your conversation history now? (y/n): ');
    if (runImportNow.toLowerCase() === 'y') {
      await runImport(pythonConfig, provider, apiKey);
    }
  }
  
  // Step 8: Configure Claude Desktop
  await setupClaudeDesktop(memoryDecay);
  
  // Done!
  header('✨ Setup Complete!');
  
  console.log('Next steps:');
  console.log('1. If using Claude Code, the reflection agent is already available');
  console.log('2. Try asking: "Find our previous discussions about [topic]"');
  console.log('3. To re-run import later: python scripts/import-openai-enhanced.py\n');
  
  success('Happy reflecting! 🎉');
  
  rl.close();
}

// Handle errors gracefully
process.on('unhandledRejection', (error) => {
  console.error('\nSetup failed with error:', error);
  rl.close();
  process.exit(1);
});

// Run the wizard
main().catch((error) => {
  console.error('\nSetup failed:', error);
  rl.close();
  process.exit(1);
});