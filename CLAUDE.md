# Claude Self Reflect - Conversation Memory for Claude

## Overview
Claude Self Reflect provides semantic search across all Claude conversations with built-in memory decay capabilities, using a vector database for efficient similarity matching.

## Architecture
- **Vector Database**: Qdrant with per-project collections
- **Embeddings**: Voyage AI (voyage-3-large, 1024 dimensions)
- **Search**: Cross-collection semantic search with time-based decay
- **Import**: Continuous file watcher for automatic updates

## Memory Decay Philosophy

### Why Decay?
Digital memory systems face a fundamental challenge: perfect recall creates imperfect utility. As conversations accumulate, finding relevant information becomes harder. Memory decay solves this by:

1. **Prioritizing Recency**: Recent conversations are more relevant
2. **Reducing Noise**: Old, outdated information fades gracefully
3. **Mimicking Human Memory**: Aligning with natural cognitive patterns
4. **Maintaining Performance**: Preventing unbounded growth issues

### Implementation
Currently using client-side decay calculation (v1.3.1):
- **Active**: Client-side exponential decay with 90-day half-life
- **Performance**: Minimal overhead (~9ms for 1000 points)

## Current Status
- **Projects Imported**: 24
- **Conversation Chunks**: 10,165+
- **Collections**: Per-project isolation with `conv_<md5>_voyage` naming
- **Search Accuracy**: 66.1% with cross-collection overhead ~100ms

## Key Commands

**📖 IMPORTANT**: For comprehensive MCP usage, see [MCP_REFERENCE.md](./MCP_REFERENCE.md)

### MCP Management in Claude Code

#### CORRECT Commands (Use These):
```bash
# List all MCPs and their connection status
claude mcp list

# Add the MCP with required environment variables (name, then command, then env vars)
claude mcp add claude-self-reflection "/Users/ramakrishnanannaswamy/projects/claude-self-reflect/claude-self-reflection/run-mcp.sh" -e VOYAGE_KEY="your-voyage-api-key" -e QDRANT_URL="http://localhost:6333"

# Remove an MCP (useful when needing to restart)
claude mcp remove claude-self-reflection

# Restart MCP (remove then re-add with env vars)
claude mcp restart claude-self-reflection
```

#### INCORRECT Commands (Never Use):
```bash
# ❌ These commands DO NOT exist:
claude mcp status claude-self-reflection  # NO SUCH COMMAND
claude mcp logs claude-self-reflection    # NO SUCH COMMAND
claude mcp add claude-self-reflection     # MISSING required commandOrUrl argument
```

#### Important Notes:
- The `claude mcp add` command REQUIRES both a name AND a commandOrUrl
- Environment variables must be passed with `-e` flag
- After adding MCP, you may need to restart Claude Code for tools to be available
- Check `.env` file for VOYAGE_KEY if not set

### Search & Reflection
```bash
# Use MCP tools in Claude
mcp__claude-self-reflection__reflect_on_past
mcp__claude-self-reflection__store_reflection
```

### Import Commands
```bash
# Always use the virtual environment
cd claude-self-reflect
source .venv/bin/activate  # or source venv/bin/activate

# Import all projects
python scripts/import-conversations-voyage.py

# Import with streaming (recommended for large files)
export VOYAGE_KEY=your-voyage-api-key  # Required for streaming import
python scripts/import-conversations-voyage-streaming.py --limit 5  # Limit to 5 files for testing

# Check collections
python scripts/check-collections.py
```

## Specialized Sub-Agents for Claude Self Reflect

### Overview
This project includes 6 specialized sub-agents that Claude will PROACTIVELY use when working on different aspects of the system. Each agent has focused expertise and will automatically activate when their domain is encountered.

**IMPORTANT**: Agents are located in `.claude/agents/` directory (NOT in a random /agents folder). They are automatically installed via npm postinstall script.

### Available Sub-Agents

1. **qdrant-specialist** - Vector database expert
   - **When to use**: Qdrant operations, collection management, embedding issues
   - **Expertise**: Collection health, search troubleshooting, dimension mismatches

2. **import-debugger** - Import pipeline specialist
   - **When to use**: Import failures, JSONL processing, zero messages issues
   - **Expertise**: JQ filters, Python scripts, conversation chunking

3. **docker-orchestrator** - Container management expert
   - **When to use**: Service failures, container restarts, compose issues
   - **Expertise**: Multi-container orchestration, health monitoring, networking

4. **mcp-integration** - MCP server developer
   - **When to use**: Claude Desktop integration, tool development, TypeScript
   - **Expertise**: MCP protocol, tool implementation, connection debugging

5. **search-optimizer** - Search quality expert
   - **When to use**: Poor search results, tuning thresholds, comparing models
   - **Expertise**: Semantic search, embedding quality, A/B testing

6. **reflection-specialist** - Conversation memory expert
   - **When to use**: Searching past conversations, storing insights, self-reflection
   - **Expertise**: Semantic search, insight storage, knowledge continuity

### Proactive Usage Examples

When you mention any of these scenarios, Claude will automatically engage the appropriate sub-agent:

```
"The import is showing 0 messages again"
→ import-debugger will investigate JQ filters and JSONL parsing

"Search results seem irrelevant"
→ search-optimizer will analyze similarity thresholds and embedding quality

"Find conversations about debugging this issue"
→ reflection-specialist will search past conversations and insights

"Remember this solution for next time"
→ reflection-specialist will store the insight with appropriate tags
```

## Project Rules
- Always activate venv before running Python scripts
- Use reflection-specialist agent for testing search functionality
- Never commit without running tests first
- Memory decay is opt-in (disabled by default)
- Test files belong in organized directories, not root
- **CRITICAL**: All agents MUST follow [MCP_REFERENCE.md](./MCP_REFERENCE.md) for MCP operations