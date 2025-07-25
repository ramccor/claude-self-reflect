#!/bin/bash

# Generate all architecture diagrams from Mermaid sources

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📊 Generating architecture diagrams...${NC}"

# Change to script directory
cd "$(dirname "$0")"

# Check if mmdc is installed
if ! command -v mmdc &> /dev/null; then
    echo "❌ Mermaid CLI (mmdc) not found!"
    echo "Install with: npm install -g @mermaid-js/mermaid-cli"
    exit 1
fi

# Generate each diagram
for mmd_file in *.mmd; do
    if [ -f "$mmd_file" ]; then
        base_name="${mmd_file%.mmd}"
        
        echo -n "• Generating ${base_name}... "
        
        # Generate PNG with high quality
        mmdc -i "$mmd_file" \
             -o "${base_name}.png" \
             -t default \
             -b white \
             -w 2048 \
             -H 1536
        
        # Also generate SVG for scalability
        mmdc -i "$mmd_file" \
             -o "${base_name}.svg" \
             -t default \
             -b transparent
        
        echo -e "${GREEN}✓${NC}"
    fi
done

echo -e "${GREEN}✅ All diagrams generated successfully!${NC}"
echo ""
echo "Generated files:"
ls -la *.png *.svg 2>/dev/null | grep -E "\.(png|svg)$" || echo "No diagrams found"