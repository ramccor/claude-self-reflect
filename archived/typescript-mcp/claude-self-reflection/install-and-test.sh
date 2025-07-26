#!/bin/bash
set -e

echo "🚀 Claude Self-Reflection Installation & Test"
echo "==========================================="
echo ""

# Check prerequisites
echo "1️⃣ Checking prerequisites..."

# Check if Qdrant is running
if ! curl -s http://localhost:6333/health > /dev/null; then
    echo "❌ Error: Qdrant is not running on localhost:6333"
    echo "Please start Qdrant first with: cd .. && docker compose up -d qdrant"
    exit 1
fi

# Check collection and count
POINTS_COUNT=$(curl -s http://localhost:6333/collections/conversations | jq -r '.result.points_count // 0')
if [ "$POINTS_COUNT" -gt 0 ]; then
    echo "✅ Qdrant is running with $POINTS_COUNT conversation chunks"
else
    echo "⚠️  Warning: No conversations found in Qdrant. You may need to run the importer."
fi

# Install and build
echo ""
echo "2️⃣ Installing dependencies..."
npm install --silent

echo ""
echo "3️⃣ Building TypeScript..."
npm run build

# Test the server
echo ""
echo "4️⃣ Testing MCP server..."
node test-server.js 2>/dev/null

echo ""
echo "5️⃣ Installation complete!"
echo ""
echo "To add this MCP server to Claude Desktop:"
echo ""
echo "Option 1 - Manual configuration:"
echo "Add this to your Claude Desktop config:"
echo ""
cat config/claude-desktop-config.json
echo ""
echo ""
echo "Option 2 - Using claude CLI (if available):"
echo "Run: claude add mcp $(pwd)/mcp.json"
echo ""
echo "Option 3 - Direct test:"
echo "The server is ready at: $(pwd)/dist/index.js"
echo ""
echo "Once added to Claude, you can use it like:"
echo "  'Use the reflect_on_past tool to search for our discussion about qdrant migration'"