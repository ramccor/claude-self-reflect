# Claude Self-Reflection MCP Query Guide

This guide provides comprehensive examples and best practices for searching your Claude conversation history using the claude-self-reflection MCP tool.

## Quick Start

The MCP tool `reflect_on_past` searches across all your imported Claude conversations using semantic search powered by Voyage AI embeddings.

### Basic Usage

```
Query: "memento stack performance"
Limit: 5
MinScore: 0.5
```

## Query Patterns & Examples

### 1. Technical Problem Solving

**Finding solutions to specific errors:**
```
✅ Good: "Python 3.13 sentencepiece build error cmake"
✅ Good: "KeyError projects state file backward compatibility"
❌ Poor: "python error"
```

**Searching for implementation details:**
```
✅ Good: "cross-collection search implementation MCP Qdrant"
✅ Good: "Voyage AI API integration bearer token"
❌ Poor: "how to implement"
```

### 2. Performance & Optimization

**Finding performance improvements:**
```
Query: "40x speed improvement 600 chunks per minute"
Intent: Find discussions about rate limit improvements and speed gains
```

**Resource optimization queries:**
```
Query: "Docker memory limits container OOM errors"
Intent: Find memory-related issues and solutions
```

### 3. Architecture & Design Decisions

**Understanding design choices:**
```
Query: "collection naming MD5 hashing project isolation"
Expected: Discussions about conv_<hash>_voyage naming pattern
```

**Migration decisions:**
```
Query: "why switch from OpenAI to Voyage embeddings accuracy"
Expected: Accuracy comparison (66.1% vs 39.2%), token limits, cost analysis
```

### 4. Progress & Status Tracking

**Project completion status:**
```
Query: "percentage Claude projects imported Voyage"
Expected: 24 projects, 100% completion, 10,165+ chunks
```

**Feature implementation status:**
```
Query: "TodoWrite completed tasks Voyage migration"
Expected: Todo items marked as completed
```

### 5. Cost & Resource Analysis

**Understanding costs:**
```
Query: "Voyage AI pricing cost analysis project size"
Expected: 200M free tokens, $0.02/M tokens pricing
```

**API limits and quotas:**
```
Query: "rate limit 3 RPM 60 RPM paid account"
Expected: Free vs paid tier differences
```

## Effective Query Strategies

### 1. Include Specific Technical Terms
```
✅ "sentencepiece cmake build error"
❌ "build problem"
```

### 2. Combine Related Concepts
```
✅ "Voyage AI embeddings 1024 dimensions accuracy"
❌ "embeddings"
```

### 3. Use Natural Language Questions
```
✅ "why did we switch from OpenAI to Voyage"
✅ "how did we solve the import getting stuck"
✅ "what was the solution for rate limiting"
```

### 4. Include Context Clues
```
✅ "memento-mcp import stuck job processing"
❌ "import stuck"
```

## Score Interpretation

- **0.8-1.0**: Excellent match - highly relevant, direct topic match
- **0.6-0.8**: Good match - relevant with related context
- **0.4-0.6**: Fair match - loosely related, may need query refinement
- **Below 0.4**: Poor match - consider different keywords

## Advanced Query Techniques

### 1. Multi-Concept Queries
Combine multiple related concepts for better results:
```
"Qdrant vector database cross-collection search Voyage embeddings"
```

### 2. Problem-Solution Pairs
Search for problems and their solutions:
```
"memento-mcp import stuck solution JQ filter optional chaining"
```

### 3. Timeline-Based Queries
Include temporal context when relevant:
```
"recent changes import script Voyage AI"
"what did we implement yesterday"
```

### 4. Comparison Queries
Find discussions comparing alternatives:
```
"OpenAI vs Voyage embeddings accuracy token limits"
"Gemini embeddings task types vs Voyage"
```

## Common Use Cases

### 1. Debugging Issues
```
Query: "how did we debug MCP not finding search results"
Intent: Find debugging steps and solutions
```

### 2. Implementation Reference
```
Query: "getVoyageCollections Promise.all parallel search"
Intent: Find code implementation details
```

### 3. Configuration Details
```
Query: "environment variables VOYAGE_KEY QDRANT_URL"
Intent: Find configuration requirements
```

### 4. Best Practices
```
Query: "best practices chunking long conversations"
Intent: Find recommendations and patterns
```

## Troubleshooting Poor Results

### If you get no results:
1. **Lower the minScore**: Try 0.3 or 0.4 instead of 0.5
2. **Use more specific terms**: Add technical details
3. **Try different word combinations**: Rephrase the concept
4. **Check spelling**: Especially for technical terms

### If results aren't relevant:
1. **Add more context**: Include related terms
2. **Be more specific**: Avoid generic terms
3. **Use exact phrases**: If you remember specific wording
4. **Increase minScore**: Filter out weak matches

## Integration Tips

### For Development Workflows
```bash
# Search for implementation patterns
"TodoWrite tool usage pattern implementation"

# Find error solutions
"TypeError cannot read property solution fix"

# Check previous decisions
"why did we choose Qdrant over Pinecone"
```

### For Documentation
```
# Find feature descriptions
"claude-self-reflection MCP features capabilities"

# Get implementation details
"how cross-collection search works implementation"
```

## Performance Considerations

- Queries typically return in < 500ms
- Cross-collection search queries all 24 projects in parallel
- Higher minScore values return faster but may miss results
- Voyage embeddings provide 66.1% accuracy vs OpenAI's 39.2%

## Future Enhancements

Based on the Gemini evaluation, future versions may support:
- Task-specific query optimization (Q&A vs retrieval)
- Query type classification for better routing
- Hybrid embedding approaches for specialized queries