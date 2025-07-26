# Architecture Details

For those who want to understand the plumbing.

## System Architecture

![Architecture Diagram](diagrams/architecture.png)

The system consists of four main components:

### 1. Claude Code/Desktop
The MCP client that requests memory operations. This is your interface to the memory system.

### 2. MCP Server
Python-based service using FastMCP framework. Provides two simple tools:
- `store_reflection` - Store important insights and decisions
- `reflect_on_past` - Search through conversation history

### 3. Import Pipeline
Python service that processes conversation logs:
- Reads JSONL files from Claude conversation logs (`~/.claude/`)
- Creates conversation chunks for context (500 tokens each)
- Generates embeddings using Voyage AI (voyage-3-large, 1024 dimensions)
- Stores directly in Qdrant with metadata

### 4. Qdrant Vector Database
- Stores conversation embeddings with metadata
- Provides fast semantic similarity search
- Built-in vector indexing and retrieval
- Local-first: your data stays on your machine
- Per-project collections for isolation

## Data Flow

1. **Import Flow**
   - Claude saves conversations to `~/.claude/projects/*/conversations/*.jsonl`
   - Import scripts read these files
   - Chunk conversations into manageable pieces
   - Generate embeddings via Voyage AI
   - Store in Qdrant with metadata (timestamp, project, etc.)

2. **Search Flow**
   - User asks Claude about past conversations
   - MCP server receives search request
   - Converts query to embedding
   - Searches Qdrant for similar vectors
   - Returns relevant conversation chunks
   - Claude presents results in context

## Project Structure

```
claude-self-reflect/
├── mcp-server/           # Python MCP server using FastMCP
│   ├── src/              # Server source code
│   │   ├── server.py     # Main MCP server implementation
│   │   └── server_v2.py  # Enhanced version with better error handling
│   ├── pyproject.toml    # Python package configuration
│   └── run-mcp.sh        # MCP startup script
├── scripts/              # Import and utility scripts
│   ├── import-*.py       # Various import scripts for conversations
│   └── test-*.py         # Test scripts for features
├── .claude/agents/       # Claude sub-agents for specialized tasks
├── config/               # Configuration files
├── data/                 # Qdrant vector database storage
└── docs/                 # Documentation and guides
```

## Technical Specifications

### Embeddings
- **Model**: Voyage AI voyage-3-large
- **Dimensions**: 1024
- **Context**: 500 tokens per chunk
- **Free tier**: 200M tokens/month

### Vector Database
- **Engine**: Qdrant
- **Storage**: Local disk
- **Collections**: Per-project isolation
- **Naming**: `conv_<md5_hash>_voyage`

### Performance
- **Search latency**: ~100ms for cross-collection search
- **Import speed**: ~1000 conversations/minute
- **Memory overhead**: ~1GB per 100k conversations

## Security & Privacy

- All data stored locally
- No cloud dependencies for core functionality
- API keys only used for embedding generation
- Conversations never leave your machine

## See Also

- [Data Flow Diagram](diagrams/data-flow.png) - Detailed flow visualization
- [Import Process](diagrams/import-process.png) - Step-by-step import workflow
- [Search Operation](diagrams/search-operation.png) - How semantic search works
- [Components Guide](components.md) - Deep dive into each component