# MCP Management in Claude Code

## Overview
When using Claude Code (not Claude Desktop), MCP servers are managed through CLI commands rather than GUI settings.

## Key Commands

### MCP Server Management
```bash
# List all configured MCP servers
claude mcp list

# Add the claude-self-reflection MCP
claude mcp add claude-self-reflect

# Remove an MCP (useful when needing to restart)
claude mcp remove claude-self-reflect

# Check MCP server status
claude mcp status claude-self-reflect

# Restart MCP after configuration changes
claude mcp restart claude-self-reflect
```

### Troubleshooting
```bash
# View MCP logs
claude mcp logs claude-self-reflect

# Debug mode for detailed output
claude mcp debug claude-self-reflect

# Test MCP connection
claude mcp test claude-self-reflect
```

### Common Issues

1. **MCP Failed to Start**
   - Check environment variables are properly set
   - Verify Qdrant is running: `docker ps | grep qdrant`
   - Check VOYAGE_KEY is configured

2. **MCP Not Finding Collections**
   - Restart the MCP: `claude mcp restart claude-self-reflect`
   - Collections are cached at startup

3. **Connection Errors**
   - Verify QDRANT_URL is correct (default: http://localhost:6333)
   - Check network connectivity to Qdrant

## Environment Configuration

The MCP uses these environment variables:
- `QDRANT_URL`: Qdrant server URL (default: http://localhost:6333)
- `VOYAGE_KEY`: API key for Voyage AI embeddings
- `ENABLE_MEMORY_DECAY`: Enable time-based decay (true/false)
- `DECAY_WEIGHT`: Decay impact (0-1, default: 0.3)
- `DECAY_SCALE_DAYS`: Half-life in days (default: 90)

## Using MCP Tools

Once connected, use the tools:
```
# Search past conversations
mcp__claude-reflect__reflect_on_past

# Store a reflection
mcp__claude-reflect__store_reflection
```

## Important Notes
- Do NOT use Claude Desktop settings when using Claude Code
- MCP servers are stdio-based and won't produce console output
- Always restart MCP after adding new collections to Qdrant