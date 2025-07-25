#!/bin/bash
# Wrapper script to run MCP server with environment variables

# Source the parent .env file if it exists
if [ -f "../.env" ]; then
    source "../.env"
fi

# Map OPENAI_KEY to OPENAI_API_KEY if needed
if [ -n "$OPENAI_KEY" ]; then
    export OPENAI_API_KEY="$OPENAI_KEY"
fi

# Map VOYAGE_KEY-2 to VOYAGE_KEY if VOYAGE_KEY is not set
if [ -z "$VOYAGE_KEY" ] && [ -n "$VOYAGE_KEY-2" ]; then
    export VOYAGE_KEY="$VOYAGE_KEY-2"
fi

# Debug logging
echo "Environment check:" >&2
echo "VOYAGE_KEY: ${VOYAGE_KEY:+Set}" >&2
echo "QDRANT_URL: $QDRANT_URL" >&2

# Run the MCP server
exec node /Users/ramakrishnanannaswamy/memento-stack/qdrant-mcp-stack/claude-self-reflection/dist/index.js "$@"