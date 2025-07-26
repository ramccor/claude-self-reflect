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

![Self Reflection vs The Grind](docs/images/red-reflection.webp)

## Before & After

### Before Claude Self-Reflect
```mermaid
flowchart LR
    A[You] -->|"What was that<br/>PostgreSQL fix?"| B[Claude]
    B -->|"I don't have access to<br/>previous conversations"| C[😤 Frustrated]
    C --> D[Search ~/.claude/logs/*]
    D --> E[grep through 10,847 matches]
    E --> F[Give up]
    F --> G[Re-solve the problem]
    
    classDef userStyle fill:#FFD700,stroke:#1e3a5f,stroke-width:3px,color:#1e3a5f
    classDef claudeStyle fill:#D2691E,stroke:#1e3a5f,stroke-width:3px,color:#fff
    classDef problemStyle fill:#1e3a5f,stroke:#FFD700,stroke-width:3px,color:#FFD700
    
    class A userStyle
    class B claudeStyle
    class C,D,E,F,G problemStyle
```

### After Claude Self-Reflect
```mermaid
flowchart LR
    A[You] -->|"What was that<br/>PostgreSQL fix?"| B[Claude]
    B -->|Spawns| C[Reflection Agent]
    C -->|MCP Protocol| D[Python Server]
    D -->|Voyage AI| E[Embeddings]
    E -->|Semantic Search| F[Qdrant DB]
    F -->|Returns matches| G[Found: GIN index<br/>2.3s → 45ms]
    G --> H[😎 Continue building]
    
    classDef userStyle fill:#FFD700,stroke:#1e3a5f,stroke-width:3px,color:#1e3a5f
    classDef claudeStyle fill:#D2691E,stroke:#1e3a5f,stroke-width:3px,color:#fff
    classDef agentStyle fill:#8B4513,stroke:#1e3a5f,stroke-width:3px,color:#fff
    classDef techStyle fill:#1e3a5f,stroke:#FFD700,stroke-width:3px,color:#FFD700
    classDef successStyle fill:#FFD700,stroke:#1e3a5f,stroke-width:3px,color:#1e3a5f
    
    class A userStyle
    class B claudeStyle
    class C agentStyle
    class D,E,F techStyle
    class G,H successStyle
```

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