# Claude-Self-Reflect - Conversation Memory for Claude

Give Claude perfect memory across all conversations. Semantic search over your entire conversation history using vector database and MCP (Model Context Protocol).

## Motivation, Alternatives & Past Attempts

**Motivation**: Claude has no memory between conversations. Every chat starts from scratch, requiring you to re-explain context, repeat solutions, and manually search through conversation files.

**Our Solution**: A semantic memory layer that automatically indexes your conversations and provides instant search through Claude's native tools.

**Past Attempts**: 
- Neo4j graph database - Too complex for simple conversation retrieval
- Keyword search - Missed semantically similar content
- Manual organization - Doesn't scale with hundreds of conversations

**Why Qdrant + Vectors**: Industry-standard approach used by LangChain, Dify, and others. Optimized for semantic similarity, not complex relationships.

## Glimpse of the Future

Imagine asking Claude:
- "What did we discuss about database design last month?"
- "Find that debugging solution we discovered together"
- "Have we encountered this error before?"

And getting instant, accurate answers from your entire conversation history. That's Claude-Self-Reflect.

## Quick Start

```bash
# One command setup - handles everything interactively
npm install -g claude-self-reflect && claude-self-reflect setup
```

**That's it!** The setup wizard will guide you through everything.

- **Need details?** See [Installation Guide](docs/installation-guide.md)
- **Embedding providers?** See [Embedding Provider Guide](docs/embedding-providers.md)
- **Manual setup?** See [Advanced Configuration](docs/installation-guide.md#manual-setup-advanced-users)

## Architecture Overview

![Architecture Diagram](docs/diagrams/architecture.png)

The system consists of four main components:
- **Claude Code/Desktop**: The MCP client that requests memory operations
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

### 2. MCP Server for Conversation Memory
- **Tool 1**: `store_reflection` - Store important insights and decisions
- **Tool 2**: `reflect_on_past` - Search through conversation history
- Simple semantic search without complex entity extraction

### 3. Python Importer
- Reads JSONL files from Claude conversation logs
- Creates conversation chunks for context
- Generates embeddings using Voyage AI (voyage-3.5-lite)
- Stores directly in Qdrant with metadata


## Using the Reflection Agent

### In Claude Code
The reflection agent activates automatically when you ask about past conversations:

![Reflection Agent in Action](docs/images/Reflection-specialist.png)

```
"What did we discuss about database design?"
"Find our previous debugging session"
"Have we encountered this error before?"
```

Or explicitly request it:
```
"Use the reflection agent to search for our API discussions"
```

### Direct Tool Usage (Advanced)
You can also ask Claude to search directly:

```
User: Can you check our past conversations about authentication?
Claude: I'll search through our conversation history about authentication...

User: Remember that we decided to use JWT tokens for the API
Claude: I'll store this decision for future reference...
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
  • Estimated cost: FREE (within 200M token limit)
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
  • 💰 Estimated cost: FREE (within 200M token limit)
```

### Cost Estimation

The dry-run mode provides accurate cost estimates:

**Free Tiers:**
- Voyage AI: 200M tokens FREE, then $0.02 per 1M tokens
- Google Gemini: Unlimited FREE (data used for training)
- Local: Always FREE

**Paid Only:**
- OpenAI: $0.02 per 1M tokens (no free tier)

**Reality Check:** With 500 tokens per conversation chunk, 200M free tokens = ~400,000 conversation chunks. Most users never reach the paid tier.

### Continuous Testing

```bash
# Test import of a single project
python scripts/import-openai-enhanced.py ~/.claude/projects/my-project --dry-run

# Monitor import progress in real-time
python scripts/import-openai-enhanced.py --dry-run | tee import-test.log
```

## 🚀 Advanced Features

### Memory Decay (v1.0.0)
Time-based relevance that prioritizes recent conversations while gradually fading older ones. Like human memory, recent discussions stay vivid while older ones gracefully fade.

- **Smart Recency**: Boost recent conversations in search results
- **Configurable Decay**: Adjust half-life from days to years
- **Per-Search Control**: Enable/disable on individual searches

See [Memory Decay Guide](docs/memory-decay.md) for configuration and usage.

## 🤝 Why Claude-Self-Reflect?

### Key Advantages
- **Local-First**: Your conversations stay on your machine
- **Zero Configuration**: Works out of the box with sensible defaults
- **Claude-Native**: Built specifically for Claude Code & Desktop  
- **Semantic Search**: Understands meaning, not just keywords
- **Continuous Import**: Automatically indexes new conversations
- **Privacy-Focused**: No data leaves your local environment


### CLAUDE.md vs Claude-Self-Reflect

| Aspect | CLAUDE.md | Claude-Self-Reflect |
|--------|-----------|-------------------|
| **Purpose** | Project-specific instructions | Conversation memory across all projects |
| **Scope** | Single project context | Global conversation history |
| **Storage** | Text file in project | Vector database (Qdrant) |
| **Search** | Exact text matching | Semantic similarity search |
| **Updates** | Manual editing | Automatic indexing |
| **Best For** | Project rules & guidelines | Finding past discussions & decisions |

**Use both together**: CLAUDE.md for project-specific rules, Claude-Self-Reflect for conversation history.



## Troubleshooting

Having issues? Check our [Troubleshooting Guide](docs/troubleshooting.md) or:

- Ask in [Discussions](https://github.com/ramakay/claude-self-reflect/discussions)
- Report bugs in [Issues](https://github.com/ramakay/claude-self-reflect/issues)

## Roadmap

**Q1 2025**: Conversation summarization, time-based filtering, export history  
**Q2 2025**: Multi-modal memory, analytics dashboard, team sharing  
**Long Term**: Active learning, conversation graphs, enterprise features

[Full Roadmap & Contributing](CONTRIBUTING.md)

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ for the Claude community by <a href="https://github.com/ramakay">ramakay</a>
</p>