# Claude Self Reflect - Conversation Memory for Claude

## Overview
Claude Self Reflect provides semantic search across all Claude conversations with built-in memory decay capabilities, using a vector database for efficient similarity matching.

## Architecture
- **Vector Database**: Qdrant with per-project collections
- **Embeddings**: FastEmbed local embeddings (all-MiniLM-L6-v2, 384 dimensions) by default, Voyage AI optional
- **Search**: Cross-collection semantic search with time-based decay
- **Import**: Continuous file watcher for automatic updates
- **MCP Server**: Python-based using FastMCP (located in `mcp-server/`)

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
- **Collections**: Per-project isolation with `conv_<md5>_local` (FastEmbed) or `conv_<md5>_voyage` (Voyage AI) naming
- **Search Accuracy**: 66.1% with cross-collection overhead ~100ms
- **Default**: Local embeddings for privacy (v2.3.7+)

## Key Commands

**📖 IMPORTANT**: For comprehensive MCP usage, see [MCP_REFERENCE.md](./MCP_REFERENCE.md)

### MCP Management in Claude Code

#### CORRECT Commands (Use These):
```bash
# List all MCPs and their connection status
claude mcp list

# Add the MCP with required environment variables (name, then command, then env vars)
claude mcp add claude-self-reflect "/Users/ramakrishnanannaswamy/projects/claude-self-reflect/mcp-server/run-mcp.sh" -e VOYAGE_KEY="your-voyage-api-key" -e QDRANT_URL="http://localhost:6333"

# Remove an MCP (useful when needing to restart)
claude mcp remove claude-self-reflect

# Restart MCP (remove then re-add with env vars)
claude mcp restart claude-self-reflect
```

#### INCORRECT Commands (Never Use):
```bash
# ❌ These commands DO NOT exist:
claude mcp status claude-self-reflect  # NO SUCH COMMAND
claude mcp logs claude-self-reflect    # NO SUCH COMMAND
claude mcp add claude-self-reflect     # MISSING required commandOrUrl argument
```

#### Important Notes:
- The `claude mcp add` command REQUIRES both a name AND a commandOrUrl
- Environment variables must be passed with `-e` flag
- After adding MCP, you may need to restart Claude Code for tools to be available
- Check `.env` file for VOYAGE_KEY if not set

### Search & Reflection
```bash
# Use MCP tools in Claude
mcp__claude-self-reflect__reflect_on_past
mcp__claude-self-reflect__store_reflection
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
   - **When to use**: Claude Code integration, tool development, TypeScript
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

## Folder Structure

```
claude-self-reflect/
├── mcp-server/           # Python MCP server using FastMCP
│   ├── src/              # Main server source code
│   ├── pyproject.toml    # Python package configuration
│   └── run-mcp.sh        # MCP startup script
├── scripts/              # Import and utility scripts
│   ├── import-*.py       # Various import scripts
│   └── test-*.py         # Test scripts
├── .claude/agents/       # Claude sub-agents for specialized tasks
├── config/               # Configuration files
├── data/                 # Qdrant data storage
├── docs/                 # Documentation
└── archived/             # Archived code (TypeScript implementation)
```

## Project Rules
- Always activate venv before running Python scripts
- Use reflection-specialist agent for testing search functionality
- Never commit without running tests first
- Memory decay is opt-in (disabled by default)
- Test files belong in organized directories, not root
- **CRITICAL**: All agents MUST follow [MCP_REFERENCE.md](./MCP_REFERENCE.md) for MCP operations

## File Organization
- Claude automatically organizes .md files based on content (see parent project's CLAUDE.md)
- **Organization Log**: If you can't find a created .md file, check `docs/organization-log.json`
  - This log tracks where files have been moved by the auto-organization system
  - It's in .gitignore so won't appear in git status
  - Future agents should consult this log when files seem to be missing

## Upgrade Guide for Existing Users

### Key Changes in v2.3.7+
1. **Local Embeddings by Default**: FastEmbed replaces Voyage AI for privacy
2. **Setup Wizard Improvements**: Better handling of existing installations
3. **Security Enhancements**: Automated scanning and vulnerability checks

### Common Upgrade Issues & Solutions

#### 1. Python Virtual Environment Conflicts
**Problem**: Setup wizard fails with "Unable to symlink python3.13" or similar
**Solution**: The setup wizard now includes health checks for existing venvs:
- Detects if venv exists but is broken/incomplete
- Checks if dependencies (fastmcp, qdrant_client) are installed
- Automatically reinstalls missing dependencies

#### 2. MCP Connection Issues After Upgrade
**Problem**: Tools not accessible after upgrade
**Solution**: 
```bash
# Remove and re-add the MCP server
claude mcp remove claude-self-reflect
claude mcp add claude-self-reflect "/path/to/mcp-server/run-mcp.sh" -e QDRANT_URL="http://localhost:6333"
# Restart Claude Code for changes to take effect
```

#### 3. Mixed Collection Types
**Problem**: Both _voyage and _local collections exist
**Solution**: This is normal! The system handles both:
- New imports use _local collections (FastEmbed)
- Old _voyage collections remain searchable
- Set PREFER_LOCAL_EMBEDDINGS=false to use Voyage AI

#### 4. Import Script Changes
**Path Changes**: 
- Old: `import-conversations-voyage.py`
- New: `import-conversations-unified.py`
- The unified script handles both embedding types

### Best Practices for Upgrading
1. **Always backup your data directory** before major upgrades
2. **Run the setup wizard** instead of manual installation
3. **Check .env settings** - new variables may be added
4. **Test with small imports first** using --limit flag
5. **Monitor Docker logs** if using containerized setup