#!/bin/bash

echo "🚀 Publishing claude-self-reflect v2.0.0 to npm"
echo ""
echo "⚠️  IMPORTANT: This is a breaking change release!"
echo ""
echo "Prerequisites:"
echo "1. You must be logged in to npm: npm login"
echo "2. You must have publish rights to the claude-self-reflect package"
echo ""
echo "This will publish:"
echo "- Version: 2.0.0"
echo "- Breaking changes: TypeScript → Python MCP server"
echo "- New design: NPM package is now an installation wizard"
echo ""
read -p "Are you ready to publish? (yes/no): " confirm

if [ "$confirm" == "yes" ]; then
    echo ""
    echo "📦 Publishing to npm..."
    npm publish
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Successfully published claude-self-reflect@2.0.0!"
        echo ""
        echo "Next steps:"
        echo "1. Test installation: npm install -g claude-self-reflect@2.0.0"
        echo "2. Monitor GitHub issues for any problems"
        echo "3. Check npm download stats"
    else
        echo ""
        echo "❌ Publishing failed. Please check your npm credentials and try again."
    fi
else
    echo ""
    echo "Publishing cancelled."
fi