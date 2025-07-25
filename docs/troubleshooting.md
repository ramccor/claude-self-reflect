# Troubleshooting Guide

## Common Issues & Solutions

### Claude can't find the MCP server

1. The reflection agent is automatically available after installation
2. For Claude Desktop, restart after configuration
3. Check if the config was added: `cat ~/Library/Application\ Support/Claude/claude_desktop_config.json`
4. Ensure Docker is running: `docker ps`
5. Check MCP server logs: `docker compose logs claude-self-reflection`

### Search returns no results

1. Verify import completed: `docker compose logs importer | grep "Import complete"`
2. Check collection has data: `curl http://localhost:6333/collections`
3. Try lowering similarity threshold: `MIN_SIMILARITY=0.5`
4. Test with exact phrases from recent conversations

### Import is slow or hanging

1. Check available memory: `docker stats`
2. Reduce batch size: `BATCH_SIZE=10`
3. Use local embeddings for testing: `USE_LOCAL_EMBEDDINGS=true`
4. Check for large conversation files: `find ~/.claude/projects -name "*.jsonl" -size +10M`

### API key errors

1. Verify your API key is correct in `.env`
2. Check API key permissions (embeddings access required)
3. Test API key directly: `curl -H "Authorization: Bearer $VOYAGE_API_KEY" https://api.voyageai.com/v1/models`
4. Try alternative provider (OpenAI vs Voyage)

## Still Need Help?

- 📚 Check our [comprehensive docs](https://github.com/ramakay/claude-self-reflect/wiki)
- 💬 Ask in [Discussions](https://github.com/ramakay/claude-self-reflect/discussions)
- 🐛 Report bugs in [Issues](https://github.com/ramakay/claude-self-reflect/issues)