# Installation Guide

## Quick Start (Claude Code)

```bash
# One command setup - handles everything interactively
npm install -g claude-self-reflect && claude-self-reflect setup
```

**That's it!** The interactive setup will:
1. Install the reflection agent automatically  
2. Guide you through choosing an embedding provider
3. Help you get API keys (with direct links)
4. Start Qdrant database (via Docker)
5. Import your Claude conversation history
6. Test that everything works

**What if I don't have Docker?** The setup will detect this and offer alternatives including local-only options.

**Already installed?** Just run `claude-self-reflect setup` to reconfigure or import new conversations.

## Manual Setup (Advanced Users)

If you prefer manual control:

### 1. Start Qdrant Database
```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest
```

### 2. Choose & Configure Embedding Provider
See [Embedding Provider Guide](embedding-providers.md) for details.

### 3. Install & Import Conversations
```bash
npm install -g claude-self-reflect
git clone https://github.com/ramakay/claude-self-reflect.git
cd claude-self-reflect
pip install -r scripts/requirements.txt
python scripts/import-openai-enhanced.py
```

## For Claude Desktop

Add to your Claude Desktop config:
```json
{
  "mcpServers": {
    "claude-self-reflect": {
      "command": "npx",
      "args": ["claude-self-reflect"],
      "env": {
        "QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
```

## Environment Variables

```bash
# Embedding Provider (choose one)
VOYAGE_API_KEY=your-key      # 200M tokens FREE, then $0.02/1M
GEMINI_API_KEY=your-key      # Unlimited FREE (data shared)
OPENAI_API_KEY=your-key      # $0.02/1M tokens (no free tier)
USE_LOCAL_EMBEDDINGS=true    # Always FREE (lower quality)

# Qdrant Configuration
QDRANT_URL=http://localhost:6333  # Default local Qdrant
```

## Performance Tuning

```bash
# For large conversation histories (>10K files)
BATCH_SIZE=100
CHUNK_SIZE=20
WORKERS=8

# For limited memory systems
BATCH_SIZE=10
CHUNK_SIZE=5
QDRANT_MEMORY=512m
```

## Multi-User Setup

```bash
# Separate collections per user
COLLECTION_PREFIX=user_${USER}

# Restrict search to specific projects
ALLOWED_PROJECTS=work,personal
```