#!/bin/bash

echo "Testing Claude Self-Reflection MCP Search..."

# Test search for Qdrant migration
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"reflect_on_past","arguments":{"query":"Qdrant migration from Neo4j","limit":3,"minScore":0.5}}}' | ./run-mcp.sh 2>/dev/null | jq -r '.result.content[0].text' | head -50