#!/bin/bash
# Wrapper script to run MCP server with environment variables

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
elif [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Source the parent .env file if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

# Map OPENAI_KEY to OPENAI_API_KEY if needed
if [ -n "$OPENAI_KEY" ]; then
    export OPENAI_API_KEY="$OPENAI_KEY"
fi

# Map VOYAGE_KEY_2 to VOYAGE_KEY if VOYAGE_KEY is not set
if [ -z "$VOYAGE_KEY" ] && [ -n "$VOYAGE_KEY_2" ]; then
    export VOYAGE_KEY="$VOYAGE_KEY_2"
fi

# Set default QDRANT_URL if not set
if [ -z "$QDRANT_URL" ]; then
    export QDRANT_URL="http://localhost:6333"
fi

# Debug logging
echo "Environment check:" >&2
echo "VOYAGE_KEY: ${VOYAGE_KEY:+Set}" >&2
echo "QDRANT_URL: $QDRANT_URL" >&2
echo "Python: $(which python)" >&2

# Run the MCP server
exec node "$SCRIPT_DIR/dist/index.js" "$@"