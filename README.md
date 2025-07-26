# Claude Self-Reflect

Claude forgets everything. This fixes that.

```bash
npm install -g claude-self-reflect && claude-self-reflect setup
```

## What You Get

Ask Claude about past conversations. Get actual answers.

**Before**: "I don't have access to previous conversations"  
**After**: "We discussed JWT auth on Tuesday. You decided on 15-minute tokens."

## The Magic

![How it works](docs/diagrams/before-after-sequence.png)

## Real Examples That Made Us Build This

```
You: "What was that PostgreSQL optimization we figured out?"
Claude: "Found it - conversation from Dec 15th. You discovered that adding 
        a GIN index on the metadata JSONB column reduced query time from 
        2.3s to 45ms."

You: "Remember that React hooks bug?"
Claude: "Yes, from last week. The useEffect was missing a dependency on 
        userId, causing stale closures in the event handler."

You: "Have we discussed WebSocket authentication before?"
Claude: "3 conversations found:
        - Oct 12: Implemented JWT handshake for Socket.io
        - Nov 3: Solved reconnection auth with refresh tokens  
        - Nov 20: Added rate limiting per authenticated connection"
```

## The Secret Sauce: Sub-Agents

Here's what makes this magical: **The Reflection Specialist sub-agent**.

When you ask about past conversations, Claude doesn't search in your main chat. Instead, it spawns a specialized sub-agent that:
- Searches your conversation history in its own context
- Brings back only the relevant results
- Keeps your main conversation clean and focused

**Your main context stays pristine**. No clutter. No token waste.

![Reflection Agent in Action](docs/images/Reflection-specialist.png)

## How It Works (10 Second Version)

Your conversations → Vector embeddings → Semantic search → Claude remembers

Technical details exist. You don't need them to start.

## Using It

Once installed, just talk naturally:

- "What did we discuss about database optimization?"
- "Find our debugging session from last week"
- "Remember this solution for next time"

The reflection specialist automatically activates. No special commands needed.

## Memory Decay

Recent conversations matter more. Old ones fade. Like your brain, but reliable.

Works perfectly out of the box. [Configure if you're particular](docs/memory-decay.md).

## For the Skeptics

**"Just use grep"** - Sure, enjoy your 10,000 matches for "database"  
**"Overengineered"** - Two functions: store_reflection, reflect_on_past  
**"Another vector DB"** - Yes, because semantic > string matching

Built by developers tired of re-explaining context every conversation.

## Requirements

- Claude Code or Claude Desktop
- Python 3.10+
- 5 minutes for setup

## Advanced Setup

Want to customize? See [Configuration Guide](docs/installation-guide.md).

## The Technical Stuff

If you must know:

- **Vector DB**: Qdrant (local, your data stays yours)
- **Embeddings**: Voyage AI (200M free tokens/month)
- **MCP Server**: Python + FastMCP
- **Search**: Semantic similarity with time decay

### Want More Details?

- [Architecture Deep Dive](docs/architecture-details.md) - How it actually works
- [Components Guide](docs/components.md) - Each piece explained
- [Why We Built This](docs/motivation-and-history.md) - The full story
- [Advanced Usage](docs/advanced-usage.md) - Power user features

## Problems?

- [Troubleshooting Guide](docs/troubleshooting.md)
- [GitHub Issues](https://github.com/ramakay/claude-self-reflect/issues)
- [Discussions](https://github.com/ramakay/claude-self-reflect/discussions)

---

Stop reading. Start installing. Your future self will thank you.

MIT License. Built with ❤️ for the Claude community.