# Memory Decay - Time-Based Relevance for Conversation Search

## Overview

Memory Decay adds time-based relevance to search results, prioritizing recent conversations while gradually fading older ones. This mimics human memory patterns where recent events are more vivid and accessible.

## Why Memory Decay?

As conversations accumulate over months and years:
- Recent discussions are often more relevant than old ones
- Technologies, decisions, and contexts change over time
- Perfect recall of everything creates information overload
- Natural forgetting helps surface what's currently important

## How It Works

### Client-Side Implementation (v1.0.0)

The current implementation applies decay calculations after retrieving search results:

```python
# Exponential decay formula
decay_factor = exp(-age_in_ms / scale_ms)
adjusted_score = original_score + (decay_weight * decay_factor)
```

**Parameters:**
- `DECAY_WEIGHT`: How much decay affects scores (0.0 to 2.0+)
- `DECAY_SCALE_DAYS`: Half-life in days (when decay_factor = 0.5)

**Example with default settings (weight=0.3, scale=90 days):**
- Fresh content: +0.3 boost to score
- 90 days old: +0.15 boost (half-life)
- 180 days old: +0.075 boost
- 1 year old: +0.03 boost (minimal)

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Enable memory decay (default: false)
ENABLE_MEMORY_DECAY=true

# Decay weight - how much to boost recent items (default: 0.3)
# - 0.0 = no decay effect
# - 0.3 = subtle boost for recent items (recommended)
# - 1.0 = moderate boost
# - 2.0 = aggressive boost (testing only)
DECAY_WEIGHT=0.3

# Half-life in days (default: 90)
# - 30 = fast decay, monthly relevance
# - 90 = quarterly relevance (recommended)
# - 180 = semi-annual relevance
# - 365 = annual relevance
DECAY_SCALE_DAYS=90
```

### Applying Changes

After modifying `.env`, restart the MCP server:

```bash
# Remove existing server
claude mcp remove claude-reflect -s user

# Re-add with new environment
claude mcp add claude-reflect /path/to/.venv/bin/claude-reflect \
  -e ENABLE_MEMORY_DECAY=true \
  -e DECAY_WEIGHT=0.3 \
  -e DECAY_SCALE_DAYS=90
```

## Usage

### Enable/Disable Per Search

Control decay on individual searches:

```python
# Force enable decay
results = await mcp.reflect_on_past(
    query="debugging React hooks",
    use_decay=1  # or "1"
)

# Force disable decay
results = await mcp.reflect_on_past(
    query="debugging React hooks", 
    use_decay=0  # or "0"
)

# Use environment default
results = await mcp.reflect_on_past(
    query="debugging React hooks",
    use_decay=-1  # or omit parameter
)
```

### Testing Memory Decay

1. **Compare with and without decay:**
```bash
# Search with decay
"Search for 'React hooks' with use_decay=1"

# Search without decay  
"Search for 'React hooks' with use_decay=0"
```

2. **Test with aggressive settings:**
```bash
# In .env
DECAY_WEIGHT=2.0
DECAY_SCALE_DAYS=30

# Recent items will get +2.0 boost
# 30-day old items get +1.0 boost
# 60-day old items get +0.5 boost
```

## Understanding Results

### Score Interpretation

With decay enabled, scores represent combined similarity + recency:
- **Base score**: Semantic similarity (0.0 to 1.0)
- **Decay boost**: Recency factor (0.0 to DECAY_WEIGHT)
- **Final score**: Can exceed 1.0 with high DECAY_WEIGHT

### Example Results

```
Without Decay (similarity only):
- "React hooks tutorial" (180 days old): 0.85
- "React hooks guide" (7 days old): 0.83
- "React hooks tips" (1 day old): 0.82

With Decay (weight=0.3, scale=90):
- "React hooks tips" (1 day old): 0.82 + 0.30 = 1.12 ⭐
- "React hooks guide" (7 days old): 0.83 + 0.28 = 1.11
- "React hooks tutorial" (180 days old): 0.85 + 0.08 = 0.93
```

Recent content wins despite slightly lower similarity!

## Limitations of v1.0.0

1. **Client-side calculation**: Fetches 3x results, then filters
2. **Performance overhead**: Extra processing for each search
3. **Incompatible with score_threshold**: Applied after retrieval

## Future: Native Qdrant Decay (v2.0.0)

Qdrant supports server-side decay functions:
- `exp_decay`: Exponential decay (like current)
- `gauss_decay`: Gaussian/bell curve decay
- `lin_decay`: Linear decay

Benefits:
- Server-side efficiency
- Proper score_threshold support
- No extra results needed
- Native integration

Stay tuned for v2.0.0 with native Qdrant decay!

## Troubleshooting

### Decay not working?
1. Check `ENABLE_MEMORY_DECAY=true` in `.env`
2. Restart MCP server (remove and re-add)
3. Use `use_decay=1` parameter explicitly
4. Check debug output in Claude logs

### Scores too high/low?
- Decrease `DECAY_WEIGHT` for subtler effect
- Increase `DECAY_SCALE_DAYS` for slower decay
- Test with dry data before production

### Need help?
- File issues: https://github.com/[username]/claude-self-reflect/issues
- Check debug logs: `~/Library/Logs/Claude/mcp-*.log`