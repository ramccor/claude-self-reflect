#!/bin/bash
# Update all paths after renaming memento-stack to claude-self-reflect

echo "Updating paths from memento-stack to claude-self-reflect..."

# Update docker-compose files
sed -i '' 's|/claude-self-reflect/|/claude-self-reflect/|g' docker-compose*.yaml 2>/dev/null

# Update environment files
sed -i '' 's|/claude-self-reflect/|/claude-self-reflect/|g' .env 2>/dev/null

# Update Dockerfiles
sed -i '' 's|/claude-self-reflect/|/claude-self-reflect/|g' Dockerfile* 2>/dev/null

# Update scripts
find scripts -name "*.py" -o -name "*.sh" -o -name "*.js" | while read file; do
    sed -i '' 's|/claude-self-reflect/|/claude-self-reflect/|g' "$file" 2>/dev/null
done

# Update claude-self-reflection directory files
if [ -d "claude-self-reflection" ]; then
    find claude-self-reflection -name "*.json" -o -name "*.js" -o -name "*.ts" -o -name "*.sh" | while read file; do
        sed -i '' 's|/claude-self-reflect/|/claude-self-reflect/|g' "$file" 2>/dev/null
    done
fi

# Update imported files state
sed -i '' 's|/claude-self-reflect/|/claude-self-reflect/|g' config-isolated/imported-files.json 2>/dev/null

# Update any CLAUDE.md files
find . -name "CLAUDE.md" | while read file; do
    sed -i '' 's|/claude-self-reflect/|/claude-self-reflect/|g' "$file" 2>/dev/null
done

echo "Path updates completed!"
echo ""
echo "Next steps:"
echo "1. Update your shell to cd to the new directory:"
echo "   cd /Users/ramakrishnanannaswamy/claude-self-reflect/qdrant-mcp-stack"
echo "2. Restart Docker containers with updated paths"
echo "3. Remove and re-add the MCP server in Claude Code"