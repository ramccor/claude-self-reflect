# Testing & Validation Guide

## Validate Your Setup

Before importing, validate that everything is configured correctly:

```bash
# Run comprehensive validation
python scripts/validate-setup.py

# Example output:
# ✅ API Key         [PASS] Voyage API key is valid
# ✅ Qdrant          [PASS] Connected to http://localhost:6333
# ✅ Claude Logs     [PASS] 24 projects, 265 files, 125.3 MB
# ✅ Disk Space      [PASS] 45.2 GB free
```

## Dry-Run Mode

Test the import process without making any changes:

```bash
# See what would be imported (no API calls, no database changes)
python scripts/import-openai-enhanced.py --dry-run

# Dry-run with preview of sample chunks
python scripts/import-openai-enhanced.py --dry-run --preview

# Validate setup only (checks connections, API keys, etc.)
python scripts/import-openai-enhanced.py --validate-only
```

### Example Dry-Run Output

```
🔍 Running in DRY-RUN mode...
============================================================
🚀 Initializing Claude-Self-Reflect Importer...

📊 Import Summary:
  • Total files: 265
  • New files to import: 265
  • Estimated chunks: ~2,650
  • Estimated cost: FREE (within 200M token limit)
  • Embedding model: voyage-3.5-lite

🔍 DRY-RUN MODE - No changes will be made

⏳ Starting import...

[DRY-RUN] Would ensure collection: conv_a1b2c3d4_voyage
[DRY-RUN] Would import 127 chunks to collection: conv_a1b2c3d4_voyage

📊 Final Statistics:
  • Time elapsed: 2 seconds
  • Projects to import: 24
  • Messages processed: 10,165
  • Chunks created: 2,650
  • Embeddings would be generated: 2,650
  • API calls would be made: 133
  • 💰 Estimated cost: FREE (within 200M token limit)
```

## Continuous Testing

```bash
# Test import of a single project
python scripts/import-openai-enhanced.py ~/.claude/projects/my-project --dry-run

# Monitor import progress in real-time
python scripts/import-openai-enhanced.py --dry-run | tee import-test.log
```

## Health Dashboard

```bash
# Check system status
./health-check.sh

# Example output:
✅ Qdrant: Healthy (1.2M vectors, 24 collections)
✅ MCP Server: Connected
✅ Import Queue: 0 pending
✅ Last Import: 2 minutes ago
✅ Search Performance: 67ms avg (last 100 queries)
```

## Useful Commands

```bash
# Validate entire setup
python scripts/validate-setup.py

# Test import without making changes
python scripts/import-openai-enhanced.py --dry-run

# View import progress
docker compose logs -f importer

# Check collection statistics
python scripts/check-collections.py

# Test search quality
npm test -- --grep "search quality"

# Backup your data
./backup.sh /path/to/backup

# Restore from backup
./restore.sh /path/to/backup
```