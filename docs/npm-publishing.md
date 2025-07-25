# NPM Publishing Guide for Claude-Self-Reflect

This guide explains how to publish the Claude-Self-Reflect package to NPM.

## Prerequisites

1. **NPM Account**: Create an account at https://www.npmjs.com/signup
2. **Package Name Availability**: Verify `claude-self-reflect` is available:
   ```bash
   npm view claude-self-reflect
   ```
   If you get a 404 error, the name is available.

## Step 1: Login to NPM

```bash
npm login
# Enter your username, password, and email
# You may need to enter a 2FA code if enabled
```

## Step 2: Verify Package Configuration

Check `claude-self-reflection/package.json`:
- `name`: "claude-self-reflect" (must be unique on NPM)
- `version`: "1.0.0" (follows semver)
- `files`: Lists which files to include in the package
- `main`: Points to the compiled output
- `publishConfig`: Set to public access

## Step 3: Build the Package

```bash
cd claude-self-reflection
npm run build
```

## Step 4: Test the Package Locally

```bash
# Create a test package
npm pack

# This creates claude-self-reflect-1.0.0.tgz
# Test installing it in another directory
cd /tmp
npm install /path/to/claude-self-reflect-1.0.0.tgz
```

## Step 5: Publish to NPM

### Manual Publishing

```bash
cd claude-self-reflection
npm publish --access public
```

### Automated Publishing (via GitHub Actions)

1. **Generate NPM Token**:
   - Go to https://www.npmjs.com/settings/YOUR_USERNAME/tokens
   - Click "Generate New Token"
   - Choose "Automation" token type
   - Copy the token

2. **Add Token to GitHub Secrets**:
   ```bash
   gh secret set NPM_TOKEN --repo ramakay/claude-self-reflect
   # Paste your token when prompted
   ```

3. **Create a GitHub Release**:
   ```bash
   # Tag the release
   git tag v1.0.1
   git push origin v1.0.1

   # Create release on GitHub
   gh release create v1.0.1 --title "v1.0.1" --notes "Bug fixes and improvements"
   ```

   The CI/CD pipeline will automatically:
   - Run tests
   - Build the package
   - Publish to NPM
   - Upload release artifacts

## Step 6: Verify Publication

```bash
# Check if published
npm view claude-self-reflect

# Install from NPM
npm install -g claude-self-reflect
```

## Version Management

When making updates:

1. **Update Version**:
   ```bash
   cd claude-self-reflection
   
   # Patch release (1.0.0 -> 1.0.1)
   npm version patch
   
   # Minor release (1.0.0 -> 1.1.0)
   npm version minor
   
   # Major release (1.0.0 -> 2.0.0)
   npm version major
   ```

2. **Push Changes**:
   ```bash
   git push origin main
   git push origin --tags
   ```

3. **Create Release**:
   ```bash
   gh release create v1.0.1 --title "v1.0.1" --notes "Description of changes"
   ```

## Best Practices

1. **Test Before Publishing**: Always test the package locally
2. **Semantic Versioning**: Follow semver conventions
3. **Documentation**: Keep README up to date
4. **Changelog**: Document changes for each release
5. **Scoped Packages**: Consider using `@username/package-name` for personal projects

## Troubleshooting

### "Package name already exists"
- Choose a different name or use a scoped package: `@ramakay/claude-self-reflect`

### "npm ERR! 402 Payment Required"
- Scoped packages require paid account for private packages
- Use `--access public` for free public scoped packages

### "npm ERR! need auth"
- Run `npm login` first
- Check `npm whoami` to verify login

## MCP-Specific Considerations

Since this is an MCP (Model Context Protocol) server:

1. **Installation Instructions**: Update README with:
   ```bash
   npm install -g claude-self-reflect
   ```

2. **Claude Desktop Config**: Document how to configure:
   ```json
   {
     "mcpServers": {
       "claude-self-reflect": {
         "command": "npx",
         "args": ["claude-self-reflect"],
         "env": {
           "QDRANT_URL": "http://localhost:6333"
         }
       }
     }
   }
   ```

3. **Global vs Local Install**: Consider both use cases in documentation