# Contributing to Claude Self-Reflection MCP

First off, thank you for considering contributing to Claude Self-Reflection! 🎉

This project aims to give Claude Desktop perfect memory of all conversations. We welcome contributions of all kinds - from bug fixes to new features, documentation improvements to performance optimizations.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Style Guidelines](#style-guidelines)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Community](#community)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/claude-self-reflection.git
   cd claude-self-reflection/qdrant-mcp-stack
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/originalowner/claude-self-reflection.git
   ```

## Development Setup

### Prerequisites

- Docker Desktop
- Node.js 18+
- Python 3.8+
- Git

### Local Development

1. **Install dependencies**:
   ```bash
   # Node.js dependencies
   cd claude-self-reflection
   npm install
   cd ..
   
   # Python dependencies
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r scripts/requirements.txt
   ```

2. **Start services**:
   ```bash
   docker compose up -d qdrant
   ```

3. **Run in development mode**:
   ```bash
   cd claude-self-reflection
   npm run dev
   ```

### Testing with Claude Desktop

1. Build the MCP server:
   ```bash
   cd claude-self-reflection
   npm run build
   ```

2. Update your Claude Desktop config to point to your local build:
   ```json
   {
     "mcpServers": {
       "claude-self-reflection-dev": {
         "command": "node",
         "args": ["/path/to/your/fork/claude-self-reflection/dist/index.js"]
       }
     }
   }
   ```

## How to Contribute

### Reporting Bugs

1. **Check existing issues** to avoid duplicates
2. **Create a new issue** with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - System information (OS, versions)
   - Relevant logs or screenshots

### Suggesting Features

1. **Check the roadmap** in README.md
2. **Open a discussion** first for major features
3. **Create a feature request** with:
   - Use case and motivation
   - Proposed implementation (if any)
   - Potential alternatives

### Code Contributions

1. **Find an issue** labeled `good first issue` or `help wanted`
2. **Comment on the issue** to claim it
3. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes** following our guidelines
5. **Test thoroughly** (see Testing section)
6. **Commit with conventional commits**:
   ```bash
   git commit -m "feat: add new search filter"
   git commit -m "fix: resolve import timeout issue"
   git commit -m "docs: update API documentation"
   ```

### Documentation

- Update README.md for user-facing changes
- Add JSDoc comments for new functions
- Update CHANGELOG.md following Keep a Changelog format
- Include code examples where helpful

## Style Guidelines

### TypeScript/JavaScript

- Use TypeScript for all new code
- Follow existing code style (2 spaces, no semicolons)
- Use meaningful variable names
- Add types for all parameters and return values
- Prefer `const` over `let`, avoid `var`

Example:
```typescript
export async function searchConversations(
  query: string,
  options: SearchOptions = {}
): Promise<SearchResult[]> {
  const { limit = 10, threshold = 0.7 } = options
  // Implementation
}
```

### Python

- Follow PEP 8
- Use type hints for Python 3.8+
- Add docstrings for all functions
- Use f-strings for formatting

Example:
```python
def process_conversation(
    content: str,
    metadata: Dict[str, Any]
) -> List[ConversationChunk]:
    """Process a conversation into searchable chunks.
    
    Args:
        content: Raw conversation text
        metadata: Conversation metadata
        
    Returns:
        List of processed chunks
    """
    # Implementation
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc)
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `test:` Test additions or fixes
- `chore:` Build process or auxiliary tool changes

## Testing

### Running Tests

```bash
# All tests
npm test

# Unit tests only
npm run test:unit

# Integration tests
npm run test:integration

# Python tests
python -m pytest scripts/tests/
```

### Writing Tests

1. **Add tests for all new features**
2. **Maintain test coverage above 80%**
3. **Use descriptive test names**
4. **Test edge cases and error conditions**

Example test:
```typescript
describe('searchConversations', () => {
  it('should return relevant results for semantic queries', async () => {
    const results = await searchConversations('React hooks')
    expect(results).toHaveLength(greaterThan(0))
    expect(results[0].score).toBeGreaterThan(0.7)
  })
  
  it('should handle empty queries gracefully', async () => {
    const results = await searchConversations('')
    expect(results).toHaveLength(0)
  })
})
```

### Performance Testing

For performance-sensitive changes:
1. Run benchmarks before and after
2. Document performance impact in PR
3. Consider memory usage, not just speed

## Submitting Changes

### Pull Request Process

1. **Update your fork**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Push your changes**:
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create a Pull Request** with:
   - Clear title following conventional commits
   - Description of changes and motivation
   - Reference to related issues
   - Screenshots/logs if applicable
   - Checklist:
     - [ ] Tests pass locally
     - [ ] Code follows style guidelines
     - [ ] Documentation updated
     - [ ] CHANGELOG.md updated

4. **Address review feedback** promptly

### Review Process

- PRs require at least one approval
- CI must pass (tests, linting)
- Maintainers may request changes
- Be patient - reviews take time

## Community

### Getting Help

- 💬 [GitHub Discussions](https://github.com/yourusername/claude-self-reflection/discussions) - Ask questions, share ideas
- 🐛 [Issue Tracker](https://github.com/yourusername/claude-self-reflection/issues) - Report bugs, request features
- 🏃‍♂️ [Discord](https://discord.gg/claude-self-reflection) - Real-time chat with community

### Recognition

Contributors are recognized in:
- README.md contributors section
- CHANGELOG.md entries
- GitHub's contributor graph

### Becoming a Maintainer

Active contributors may be invited to become maintainers. Maintainers can:
- Merge pull requests
- Manage issues and discussions
- Guide project direction
- Represent the project

## Thank You! 🙏

Every contribution helps make Claude's memory better. Whether it's fixing a typo, adding a feature, or helping others in discussions - we appreciate your time and effort!

Happy coding! 🚀