#!/bin/bash
set -e

echo "🚀 Installing claude-self-reflection..."

# Check if Qdrant is running
if ! curl -s http://localhost:6333/health > /dev/null; then
    echo "❌ Error: Qdrant is not running on localhost:6333"
    echo "Please start Qdrant first with: docker compose up -d qdrant"
    exit 1
fi

# Check if conversations collection exists
if curl -s http://localhost:6333/collections/conversations | grep -q "status\":\"green"; then
    echo "✅ Qdrant conversations collection found"
else
    echo "⚠️  Warning: conversations collection not found. You may need to run the importer first."
fi

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Build TypeScript
echo "🔨 Building TypeScript..."
npm run build

echo "✅ Installation complete!"
echo ""
echo "To use with Claude Desktop, add this to your Claude Desktop config:"
echo ""
cat config/claude-desktop-config.json
echo ""
echo "To test locally, run: npm start"