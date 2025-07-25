# Claude-Self-Reflect (CSR) - Conversation Memory for Claude Desktop

A streamlined implementation of conversation memory using Qdrant vector database and MCP (Model Context Protocol). This replaces the complex Neo4j graph-based approach with a simpler, more maintainable semantic search solution.

## Architecture Overview

![Architecture Diagram](docs/diagrams/architecture.png)

The system consists of four main components:
- **Claude Desktop**: The MCP client that requests memory operations
- **MCP Server**: TypeScript service providing search and store tools
- **Import Pipeline**: Python service that processes conversation logs
- **Qdrant Database**: Vector storage with semantic search capabilities

See also:
- [Data Flow Diagram](docs/diagrams/data-flow.png) - How data moves through the system
- [Import Process](docs/diagrams/import-process.png) - Detailed import workflow
- [Search Operation](docs/diagrams/search-operation.png) - How semantic search works

## Why Qdrant Over Neo4j?

1. **Simplicity**: Two tools (store/find) vs complex entity/relationship management
2. **Performance**: Optimized for semantic search, no graph traversal overhead
3. **Proven Pattern**: Industry standard for conversation memory (LangChain, Dify, etc.)
4. **No Import Issues**: Direct vector storage without entity extraction complexity

## Components

### 1. Qdrant Vector Database
- Stores conversation embeddings with metadata
- Provides fast semantic similarity search
- Built-in vector indexing and retrieval

### 2. Qdrant MCP Server
- **Tool 1**: `qdrant-store` - Store conversation memories
- **Tool 2**: `qdrant-find` - Retrieve relevant memories by semantic search
- No complex entity extraction or relationship mapping

### 3. Python Importer
- Reads JSONL files from Claude Desktop logs
- Creates conversation chunks for context
- Generates embeddings using sentence-transformers
- Stores directly in Qdrant with metadata

## Quick Start

1. **Start the services:**
```bash
docker compose up -d
```

2. **Run initial import:**
```bash
docker compose run --rm importer
```

3. **Configure Claude Desktop:**
Add to your Claude Desktop config:
```json
{
  "mcpServers": {
    "qdrant-memory": {
      "command": "docker",
      "args": ["compose", "exec", "-T", "qdrant-mcp", "mcp-server-qdrant"],
      "cwd": "/path/to/qdrant-mcp-stack"
    }
  }
}
```

## Usage Examples

### Store a memory:
```
Claude: Use the qdrant-store tool to remember "We discussed implementing a chat memory system using Qdrant instead of Neo4j for simplicity"
```

### Find memories:
```
Claude: Use the qdrant-find tool to search for "chat memory implementation"
```

## 🧪 Testing & Dry-Run Mode

### Validate Your Setup

Before importing, validate that everything is configured correctly:

```bash
# Run comprehensive validation
python scripts/validate-setup.py

# Example output:
# ✅ API Key         [PASS] Voyage API key is valid
# ✅ Qdrant          [PASS] Connected to http://localhost:6333
# ✅ Claude Logs     [PASS] 24 projects, 265 files, 125.3 MB
# ✅ Disk Space      [PASS] 45.2 GB free
```

### Dry-Run Mode

Test the import process without making any changes:

```bash
# See what would be imported (no API calls, no database changes)
python scripts/import-openai-enhanced.py --dry-run

# Dry-run with preview of sample chunks
python scripts/import-openai-enhanced.py --dry-run --preview

# Validate setup only (checks connections, API keys, etc.)
python scripts/import-openai-enhanced.py --validate-only
```

### Example Dry-Run Output

```
🔍 Running in DRY-RUN mode...
============================================================
🚀 Initializing Claude-Self-Reflect Importer...

📊 Import Summary:
  • Total files: 265
  • New files to import: 265
  • Estimated chunks: ~2,650
  • Estimated cost: $0.0265
  • Embedding model: voyage-3.5-lite

🔍 DRY-RUN MODE - No changes will be made

⏳ Starting import...

[DRY-RUN] Would ensure collection: conv_a1b2c3d4_voyage
[DRY-RUN] Would import 127 chunks to collection: conv_a1b2c3d4_voyage

📊 Final Statistics:
  • Time elapsed: 2 seconds
  • Projects to import: 24
  • Messages processed: 10,165
  • Chunks created: 2,650
  • Embeddings would be generated: 2,650
  • API calls would be made: 133
  • 💰 Estimated cost: $0.0265
```

### Cost Estimation

The dry-run mode provides accurate cost estimates based on:
- Voyage AI: $0.02 per 1M tokens (voyage-3.5-lite)
- OpenAI: $0.13 per 1M tokens (text-embedding-3-small)
- Average 500 tokens per conversation chunk

### Continuous Testing

```bash
# Test import of a single project
python scripts/import-openai-enhanced.py ~/.claude/projects/my-project --dry-run

# Monitor import progress in real-time
python scripts/import-openai-enhanced.py --dry-run | tee import-test.log
```

## 🤝 Comparison with Other Solutions

### Why Claude-Self-Reflect (CSR) Wins

| Feature | Claude-Self-Reflect | mem0 | Langchain Memory | Custom Solutions |
|---------|------------------------|------|------------------|------------------|
| **Setup Time** | 5 minutes | 30+ minutes | 1+ hours | Days |
| **Claude Desktop Integration** | ✅ Native MCP | ❌ Manual | ❌ Not supported | ❌ Complex |
| **Semantic Search** | ✅ State-of-art | ✅ Basic | ✅ Good | ❓ Varies |
| **Auto-Import** | ✅ Continuous | ❌ Manual | ❌ Manual | ❌ Manual |
| **Privacy** | ✅ 100% Local | ❌ Cloud | ❓ Depends | ✅ Local |
| **Production Ready** | ✅ Yes | ⚠️ Beta | ✅ Yes | ❌ No |

### Our Secret Sauce 🌟

1. **MCP-First Design** - Built specifically for Claude Desktop, not retrofitted
2. **Conversation-Aware Chunking** - Preserves context across messages
3. **Cross-Project Search** - Search all your projects simultaneously  
4. **Zero-Config Import** - Automatically finds and imports all conversations
5. **Continuous Learning** - Watches for new conversations in real-time

## 🧑‍💻 For Developers

### NPM Package

```bash
npm install claude-self-reflect
```

```javascript
import { ClaudeSelfReflect } from 'claude-self-reflect';

const memory = new ClaudeSelfReflect({
  qdrantUrl: 'http://localhost:6333',
  embeddingProvider: 'voyage', // or 'openai' or 'local'
  apiKey: process.env.VOYAGE_API_KEY
});

// Search conversations
const results = await memory.search('React hooks');

// Store new memory
await memory.store({
  content: 'Discussed React performance optimization',
  metadata: { project: 'my-app', timestamp: Date.now() }
});
```

### Contributing

We love contributions! Check out our [Contributing Guide](CONTRIBUTING.md) for:

- 🐛 Bug reports and fixes
- ✨ Feature requests and implementations
- 📚 Documentation improvements
- 🧪 Test coverage expansion

## 🛠️ Advanced Configuration

### Custom Embedding Models

```bash
# Use OpenAI's latest model
EMBEDDING_MODEL=text-embedding-3-large

# Use Voyage's latest model  
EMBEDDING_MODEL=voyage-3

# Use a custom Hugging Face model
EMBEDDING_MODEL=intfloat/e5-large-v2
```

### Performance Tuning

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

### Multi-User Setup

```bash
# Separate collections per user
COLLECTION_PREFIX=user_${USER}

# Restrict search to specific projects
ALLOWED_PROJECTS=work,personal
```

## 📊 Monitoring & Maintenance

### Health Dashboard

```bash
# Check system status
./health-check.sh

# Example output:
✅ Qdrant: Healthy (1.2M vectors, 24 collections)
✅ MCP Server: Connected
✅ Import Queue: 0 pending
✅ Last Import: 2 minutes ago
✅ Search Performance: 67ms avg (last 100 queries)
```

### Useful Commands

```bash
# Validate entire setup
python scripts/validate-setup.py

# Test import without making changes
python scripts/import-openai-enhanced.py --dry-run

# View import progress
docker compose logs -f importer

# Check collection statistics
python scripts/check-collections.py

# Test search quality
npm test -- --grep "search quality"

# Backup your data
./backup.sh /path/to/backup

# Restore from backup
./restore.sh /path/to/backup
```

## 🔧 Troubleshooting

### Common Issues & Solutions

<details>
<summary><b>Claude can't find the MCP server</b></summary>

1. Restart Claude Desktop after installation
2. Check if the config was added: `cat ~/Library/Application\ Support/Claude/claude_desktop_config.json`
3. Ensure Docker is running: `docker ps`
4. Check MCP server logs: `docker compose logs claude-self-reflection`

</details>

<details>
<summary><b>Search returns no results</b></summary>

1. Verify import completed: `docker compose logs importer | grep "Import complete"`
2. Check collection has data: `curl http://localhost:6333/collections`
3. Try lowering similarity threshold: `MIN_SIMILARITY=0.5`
4. Test with exact phrases from recent conversations

</details>

<details>
<summary><b>Import is slow or hanging</b></summary>

1. Check available memory: `docker stats`
2. Reduce batch size: `BATCH_SIZE=10`
3. Use local embeddings for testing: `USE_LOCAL_EMBEDDINGS=true`
4. Check for large conversation files: `find ~/.claude/projects -name "*.jsonl" -size +10M`

</details>

<details>
<summary><b>API key errors</b></summary>

1. Verify your API key is correct in `.env`
2. Check API key permissions (embeddings access required)
3. Test API key directly: `curl -H "Authorization: Bearer $VOYAGE_API_KEY" https://api.voyageai.com/v1/models`
4. Try alternative provider (OpenAI vs Voyage)

</details>

### Still Need Help?

- 📚 Check our [comprehensive docs](https://github.com/ramakay/claude-self-reflect/wiki)
- 💬 Ask in [Discussions](https://github.com/ramakay/claude-self-reflect/discussions)
- 🐛 Report bugs in [Issues](https://github.com/ramakay/claude-self-reflect/issues)

## 🚢 Roadmap

### Near Term (Q1 2025)
- [x] One-command installation
- [x] Continuous import watching
- [x] Cross-project search
- [ ] Conversation summarization
- [ ] Time-based filtering
- [ ] Export conversation history

### Medium Term (Q2 2025)
- [ ] Multi-modal memory (images, code blocks)
- [ ] Conversation analytics dashboard
- [ ] Team sharing capabilities
- [ ] Cloud sync option (encrypted)
- [ ] VS Code extension

### Long Term (2025+)
- [ ] Active learning from search patterns
- [ ] Conversation graph visualization
- [ ] Integration with other AI assistants
- [ ] Enterprise features

## 🙏 Acknowledgments

- [Anthropic](https://anthropic.com) for Claude and the MCP protocol
- [Qdrant](https://qdrant.tech) for the amazing vector database
- [Voyage AI](https://voyageai.com) for best-in-class embeddings
- All our [contributors](https://github.com/ramakay/claude-self-reflect/graphs/contributors)

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <i>Built with ❤️ for the Claude community</i><br>
  <b>Star ⭐ this repo if it helps you remember!</b>
</p>