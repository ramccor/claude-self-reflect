#!/bin/bash

# Claude Self-Reflection MCP - Health Check Script
# Displays system status and health information

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Qdrant health
echo -e "${BLUE}🔍 Checking system health...${NC}"
echo ""

# Check if Qdrant is running
if curl -s http://localhost:6333/health | grep -q "ok"; then
    # Get collection stats
    COLLECTIONS=$(curl -s http://localhost:6333/collections | jq -r '.result.collections | length')
    TOTAL_VECTORS=0
    
    if [ "$COLLECTIONS" -gt 0 ]; then
        # Sum up vectors across all collections
        for collection in $(curl -s http://localhost:6333/collections | jq -r '.result.collections[].name'); do
            COUNT=$(curl -s "http://localhost:6333/collections/$collection" | jq -r '.result.vectors_count // 0')
            TOTAL_VECTORS=$((TOTAL_VECTORS + COUNT))
        done
    fi
    
    echo -e "${GREEN}✅ Qdrant:${NC} Healthy (${TOTAL_VECTORS} vectors, ${COLLECTIONS} collections)"
else
    echo -e "${RED}❌ Qdrant:${NC} Not responding"
fi

# Check MCP Server
MCP_PID=$(pgrep -f "node.*claude-self-reflection" || true)
if [ -n "$MCP_PID" ]; then
    echo -e "${GREEN}✅ MCP Server:${NC} Connected (PID: $MCP_PID)"
else
    echo -e "${YELLOW}⚠️  MCP Server:${NC} Not running (start Claude Desktop)"
fi

# Check import status
if [ -f config/imported-files.json ]; then
    IMPORTED_COUNT=$(jq -r '. | length' config/imported-files.json)
    LAST_IMPORT=$(jq -r '. | to_entries | max_by(.value.imported_at).value.imported_at' config/imported-files.json 2>/dev/null || echo "never")
    
    if [ "$LAST_IMPORT" != "never" ]; then
        # Calculate time since last import
        LAST_TIMESTAMP=$(date -d "$LAST_IMPORT" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "$LAST_IMPORT" +%s 2>/dev/null || echo 0)
        NOW=$(date +%s)
        DIFF=$((NOW - LAST_TIMESTAMP))
        
        if [ $DIFF -lt 3600 ]; then
            TIME_AGO="$((DIFF / 60)) minutes ago"
        elif [ $DIFF -lt 86400 ]; then
            TIME_AGO="$((DIFF / 3600)) hours ago"
        else
            TIME_AGO="$((DIFF / 86400)) days ago"
        fi
    else
        TIME_AGO="never"
    fi
    
    echo -e "${GREEN}✅ Import Queue:${NC} 0 pending ($IMPORTED_COUNT files imported)"
    echo -e "${GREEN}✅ Last Import:${NC} $TIME_AGO"
else
    echo -e "${YELLOW}⚠️  Import Status:${NC} No imports yet"
fi

# Check search performance (if test results exist)
if [ -f claude-self-reflection/test-results.json ]; then
    AVG_TIME=$(jq -r '.searchPerformance.avgResponseTime' claude-self-reflection/test-results.json 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✅ Search Performance:${NC} ${AVG_TIME}ms avg (last test run)"
else
    echo -e "${BLUE}ℹ️  Search Performance:${NC} No test data available"
fi

# Check Docker resources
echo ""
echo -e "${BLUE}📊 Resource Usage:${NC}"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep -E "(claude-reflection|CONTAINER)" || echo "No containers running"

# Check for updates
echo ""
echo -e "${BLUE}🔄 Update Check:${NC}"
if [ -d .git ]; then
    git fetch --quiet
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse @{u})
    
    if [ "$LOCAL" = "$REMOTE" ]; then
        echo -e "✅ You're up to date!"
    else
        echo -e "${YELLOW}⚠️  Updates available! Run: git pull && ./install.sh${NC}"
    fi
else
    echo "Not a git repository - can't check for updates"
fi

echo ""
echo -e "${BLUE}💡 Quick Actions:${NC}"
echo "• Import new conversations: docker compose run --rm importer"
echo "• View logs: docker compose logs -f"
echo "• Run tests: cd claude-self-reflection && npm test"
echo "• Check collections: python scripts/check-collections.py"