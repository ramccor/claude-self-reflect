# How to Restart Claude Self-Reflection MCP

When new collections are added to Qdrant, the MCP server needs to be restarted to discover them.

## Quick Steps:

1. **In Claude Desktop:**
   - Open Settings (⌘+,)
   - Go to "MCP Servers" section
   - Find "claude-self-reflect"
   - Click the trash icon to remove it
   - Click "Add Server" and re-add:
     ```json
     {
       "command": "node",
       "args": ["/Users/ramakrishnanannaswamy/claude-self-reflect/qdrant-mcp-stack/claude-self-reflection/dist/index.js"],
       "env": {
         "QDRANT_URL": "http://localhost:6333",
         "VOYAGE_KEY": "your-key-here",
         "ENABLE_MEMORY_DECAY": "true",
         "DECAY_WEIGHT": "0.3",
         "DECAY_SCALE_DAYS": "90"
       }
     }
     ```

2. **Alternative - Restart Claude Desktop:**
   - Quit Claude Desktop completely (⌘+Q)
   - Restart Claude Desktop
   - The MCP will reload and discover all collections

## Why This Is Needed:

The MCP caches the list of collections at startup. When new collections are added (like `conv_b2795adc_voyage` for today's conversation), the MCP needs to refresh its collection list.

## Verify It Worked:

After restarting, test with:
```
"Find conversations about memory decay implementation"
```

You should now see results from today's conversation!