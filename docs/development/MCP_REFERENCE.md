# MCP Reference Guide - CRITICAL FOR ALL AGENTS

This document contains CRITICAL information that ALL agents MUST follow when working with MCPs (Model Context Protocol servers).

## 🚨 CRITICAL MCP RULES - NEVER VIOLATE THESE

### 1. MCP Tool Naming Convention
**CORRECT**: When calling MCP tools in Claude Code, ALWAYS use the namespaced format:
```
mcp__<server-name>__<tool-name>
```

**Example for claude-self-reflect**:
- ✅ CORRECT: `mcp__claude-self-reflect__reflect_on_past`
- ✅ CORRECT: `mcp__claude-self-reflect__store_reflection`
- ❌ WRONG: `reflect_on_past` (missing namespace)
- ❌ WRONG: `mcp__claude-self-reflection__reflect_on_past` (wrong server name)

### 2. MCP Management Commands

#### ✅ CORRECT Commands (ONLY use these):
```bash
# List all MCPs and their connection status
claude mcp list

# Add MCP with environment variables (ORDER MATTERS: name, command, then flags)
claude mcp add <name> <command-or-path> -e KEY=value -e KEY2=value2

# Remove an MCP
claude mcp remove <name>

# Restart MCP (built-in command)
claude mcp restart <name>
```

#### ❌ INCORRECT Commands (NEVER use these):
```bash
claude mcp status <name>     # ❌ NO SUCH COMMAND
claude mcp logs <name>       # ❌ NO SUCH COMMAND  
claude mcp add <name>        # ❌ MISSING required commandOrUrl
```

### 3. Adding claude-self-reflect MCP

**CORRECT full command**:
```bash
claude mcp add claude-self-reflect "/Users/ramakrishnanannaswamy/projects/claude-self-reflect/mcp-server/run-mcp.sh" -e VOYAGE_KEY="<actual-key>" -e QDRANT_URL="http://localhost:6333"
```

**Common mistakes to AVOID**:
- ❌ Wrong order: `claude mcp add -e KEY=value claude-self-reflect /path`
- ❌ Missing command: `claude mcp add claude-self-reflect`
- ❌ Wrong path: Using relative paths instead of absolute
- ❌ Missing env vars: Not including required VOYAGE_KEY

### 4. MCP Tool Availability

**IMPORTANT**: After adding an MCP:
1. Tools may NOT be immediately available in current session
2. May need to restart Claude Code for tools to appear
3. Always verify with `claude mcp list` first
4. If tools don't work, check the namespaced format

### 5. Testing MCP Functionality

**Correct testing sequence**:
1. Check if MCP is connected: `claude mcp list`
2. Use namespaced tool names: `mcp__claude-self-reflect__reflect_on_past`
3. If tools fail, don't assume they don't exist - check namespace
4. If still failing, restart Claude Code

## 🎯 Quick Reference for claude-self-reflect

### Available Tools:
- `mcp__claude-self-reflect__reflect_on_past` - Search past conversations
- `mcp__claude-self-reflect__store_reflection` - Store insights

### Required Environment Variables:
- `VOYAGE_KEY`: API key for Voyage AI embeddings
- `QDRANT_URL`: Vector database URL (default: http://localhost:6333)

### Common Operations:

**Search for past conversations**:
```javascript
mcp__claude-self-reflect__reflect_on_past({
  query: "your search query",
  limit: 5,
  minScore: 0.7
})
```

**Store a reflection**:
```javascript
mcp__claude-self-reflect__store_reflection({
  content: "Important insight or solution",
  tags: ["tag1", "tag2", "tag3"]
})
```

## 🛠️ Troubleshooting Guide

### Issue: "No such tool available"
1. Check you're using namespaced format: `mcp__server-name__tool-name`
2. Verify MCP is connected: `claude mcp list`
3. Restart Claude Code if needed

### Issue: "Missing required argument 'commandOrUrl'"
- You forgot the command/path in `claude mcp add`
- Correct: `claude mcp add <name> <path> -e KEY=value`

### Issue: MCP not connecting
1. Check Qdrant is running: `docker ps | grep qdrant`
2. Verify environment variables are correct
3. Check run-mcp.sh has execute permissions

## 📋 Agent Checklist

Before working with MCPs, ALWAYS:
- [ ] Know the exact MCP server name (e.g., `claude-self-reflect`)
- [ ] Use namespaced tool format: `mcp__<server>__<tool>`
- [ ] Include all required parameters when adding MCPs
- [ ] Verify connection with `claude mcp list`
- [ ] Remember that `claude mcp status` and `claude mcp logs` DON'T EXIST

## 🚀 Copy-Paste Commands

```bash
# Remove and re-add claude-self-reflect (update VOYAGE_KEY)
claude mcp remove claude-self-reflect
claude mcp add claude-self-reflect "/Users/ramakrishnanannaswamy/projects/claude-self-reflect/mcp-server/run-mcp.sh" -e VOYAGE_KEY="your-actual-key" -e QDRANT_URL="http://localhost:6333"
claude mcp list
```

---

**REMEMBER**: When in doubt, refer to this document. These rules are ABSOLUTE and must NEVER be violated by any agent.