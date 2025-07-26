#!/usr/bin/env node
/**
 * Test specific queries through the MCP to validate real-world usage
 */

interface MCPTestQuery {
  description: string;
  query: string;
  expectedContext: string;
  minScore?: number;
  limit?: number;
}

export const MCP_TEST_QUERIES: MCPTestQuery[] = [
  // Performance and optimization queries
  {
    description: "Check if we looked at performance optimization",
    query: "did we look at performance optimization for the memento project",
    expectedContext: "Should find discussions about performance, optimization strategies, or speed improvements",
    minScore: 0.5
  },
  {
    description: "Find rate limiting discussions",
    query: "what were the rate limit issues and how did we solve them",
    expectedContext: "Should find mentions of 3 RPM free tier, 60 RPM paid tier, and the 40x speed improvement",
    minScore: 0.6
  },

  // Technical implementation queries
  {
    description: "Search for embedding migration details",
    query: "why did we switch from OpenAI to Voyage AI embeddings",
    expectedContext: "Should find accuracy comparison (39.2% vs 66.1%), token limits (8k vs 32k), and cost analysis",
    minScore: 0.7
  },
  {
    description: "Find Python compatibility issues",
    query: "Python 3.13 sentencepiece compatibility Docker solution",
    expectedContext: "Should find discussions about build errors, CMake issues, and the Docker Python 3.11 solution",
    minScore: 0.6
  },

  // Solution-finding queries
  {
    description: "Look for implemented solutions",
    query: "what was the solution for the memento-mcp import getting stuck",
    expectedContext: "Should find mentions of JQ filter fixes, optional chaining operators, and import pipeline issues",
    minScore: 0.5
  },
  {
    description: "Find cross-collection search implementation",
    query: "how did we implement cross-collection search in the MCP",
    expectedContext: "Should find code showing getVoyageCollections() and Promise.all for parallel searches",
    minScore: 0.6
  },

  // Status and progress queries
  {
    description: "Check project completion status",
    query: "what percentage of Claude projects have been imported with Voyage",
    expectedContext: "Should find mentions of 24 projects, 100% completion, 10,165+ chunks",
    minScore: 0.5
  },
  {
    description: "Find todo list progress",
    query: "TodoWrite completed tasks Voyage migration",
    expectedContext: "Should find todo items marked as completed for Voyage AI migration tasks",
    minScore: 0.6
  },

  // Cost and resource queries
  {
    description: "Search for cost analysis",
    query: "Voyage AI pricing cost analysis for our project size",
    expectedContext: "Should find 200M free tokens, $0.02/M tokens pricing, and project size estimates",
    minScore: 0.6
  },
  {
    description: "Find memory and resource discussions",
    query: "Docker memory limits container configuration",
    expectedContext: "Should find mentions of 2GB memory limits, OOM errors, and container configuration",
    minScore: 0.5
  },

  // Debugging and troubleshooting queries
  {
    description: "Search for debugging steps",
    query: "how did we debug the MCP not finding search results",
    expectedContext: "Should find mentions of environment variables, API key configuration, and field mapping fixes",
    minScore: 0.5
  },
  {
    description: "Find error resolution patterns",
    query: "KeyError projects state file backward compatibility",
    expectedContext: "Should find the state file format conversion fix for the projects field",
    minScore: 0.6
  },

  // Architecture and design queries
  {
    description: "Search for architecture decisions",
    query: "collection naming strategy MD5 hashing project isolation",
    expectedContext: "Should find discussions about conv_<hash>_voyage naming pattern and project isolation",
    minScore: 0.6
  },
  {
    description: "Find embedding dimension discussions",
    query: "embedding dimensions 384 1536 1024 migration",
    expectedContext: "Should find the progression from sentence-transformers (384) to OpenAI (1536) to Voyage (1024)",
    minScore: 0.7
  },

  // Feature and capability queries
  {
    description: "Search for MCP capabilities",
    query: "what search features does the claude-self-reflection MCP support",
    expectedContext: "Should find cross-collection search, semantic search, score thresholds, and project filtering",
    minScore: 0.5
  },
  {
    description: "Find API integration details",
    query: "Voyage API integration bearer token authentication",
    expectedContext: "Should find API endpoint, authentication headers, and model configuration",
    minScore: 0.6
  }
];

/**
 * Format a test query for display
 */
export function formatTestQuery(query: MCPTestQuery): string {
  return `
### ${query.description}
**Query**: "${query.query}"
**Expected**: ${query.expectedContext}
**Min Score**: ${query.minScore || 0.5}
**Limit**: ${query.limit || 5}
`;
}

/**
 * Generate documentation examples from test queries
 */
export function generateQueryExamples(): string {
  const examples = MCP_TEST_QUERIES.map(q => formatTestQuery(q)).join('\n');
  
  return `# Claude Self-Reflection MCP Query Examples

These examples demonstrate effective search queries for the claude-self-reflection MCP tool.

## Query Patterns

${examples}

## Tips for Effective Queries

1. **Be specific with technical terms**: Include exact error messages, tool names, or technical concepts
2. **Use natural language**: The system understands questions like "why did we..." or "how did we solve..."
3. **Include context**: Add project names, time references, or specific features you're looking for
4. **Combine related terms**: "Voyage AI embeddings accuracy" is better than just "embeddings"
5. **Ask about solutions**: "what was the solution for..." helps find resolved issues

## Score Interpretation

- **0.8-1.0**: Excellent match - highly relevant results
- **0.6-0.8**: Good match - relevant with some context
- **0.4-0.6**: Fair match - loosely related content
- **Below 0.4**: Poor match - consider refining your query
`;
}

// Export for testing
export default MCP_TEST_QUERIES;