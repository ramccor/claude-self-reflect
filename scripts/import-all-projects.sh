#!/bin/bash
# Import all Claude projects one by one to avoid memory issues

CLAUDE_PROJECTS_DIR="$HOME/.claude/projects"
SCRIPT_DIR="$(dirname "$0")"
PYTHON_SCRIPT="$SCRIPT_DIR/import-single-project.py"

echo "Starting systematic import of all Claude projects..."
echo "Projects directory: $CLAUDE_PROJECTS_DIR"

# Count total projects
TOTAL_PROJECTS=$(ls -1 "$CLAUDE_PROJECTS_DIR" | wc -l)
echo "Found $TOTAL_PROJECTS projects to process"

# Process each project
COUNTER=0
for PROJECT_DIR in "$CLAUDE_PROJECTS_DIR"/*; do
    if [ -d "$PROJECT_DIR" ]; then
        COUNTER=$((COUNTER + 1))
        PROJECT_NAME=$(basename "$PROJECT_DIR")
        echo ""
        echo "[$COUNTER/$TOTAL_PROJECTS] Processing: $PROJECT_NAME"
        echo "----------------------------------------"
        
        # Run the single project importer
        python3 "$PYTHON_SCRIPT" "$PROJECT_DIR"
        
        # Small delay to avoid overwhelming the system
        sleep 2
    fi
done

echo ""
echo "Import complete! Processed $COUNTER projects."

# Show final statistics
echo ""
echo "Collection statistics:"
curl -s http://localhost:6333/collections | \
    jq -r '.result.collections[] | select(.name | startswith("conv_")) | "\(.name): \(.points_count // 0) points"' | \
    sort