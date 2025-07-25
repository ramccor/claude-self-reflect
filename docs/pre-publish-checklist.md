# Pre-Publish Checklist for NPM

Complete these steps before publishing to NPM:

## Code Quality
- [ ] All tests passing locally
- [ ] CI/CD pipeline green on main branch
- [ ] No console.log statements in production code
- [ ] TypeScript builds without errors
- [ ] ESLint passes without warnings

## Documentation
- [ ] README.md is up to date
- [ ] Installation instructions are clear
- [ ] Configuration examples provided
- [ ] API documentation complete
- [ ] CHANGELOG.md updated

## Package Configuration
- [ ] package.json version bumped appropriately
- [ ] Dependencies are production-ready (no local paths)
- [ ] "files" field includes all necessary files
- [ ] "files" field excludes unnecessary files (tests, docs, etc.)
- [ ] License file included

## Security
- [ ] No hardcoded API keys or secrets
- [ ] Dependencies audited: `npm audit`
- [ ] No vulnerable dependencies
- [ ] .npmignore or files field properly configured

## Testing
- [ ] Package builds successfully: `npm run build`
- [ ] Package can be packed: `npm pack`
- [ ] Test package installs locally
- [ ] MCP server starts correctly
- [ ] Basic functionality works

## Pre-Publish Commands

```bash
# 1. Clean install and build
rm -rf node_modules dist
npm ci
npm run build

# 2. Run all tests
npm test

# 3. Security audit
npm audit

# 4. Test package locally
npm pack
# Check the .tgz file size (should be reasonable)
tar -tzf claude-self-reflect-*.tgz | head -20

# 5. Dry run (see what would be published)
npm publish --dry-run
```

## Manual Publishing Process

```bash
# 1. Login to NPM
npm login

# 2. Publish
npm publish --access public

# 3. Verify
npm view claude-self-reflect
```

## Post-Publish

- [ ] Test installation from NPM: `npm install -g claude-self-reflect`
- [ ] Update GitHub release notes
- [ ] Announce on relevant channels
- [ ] Monitor NPM download stats
- [ ] Watch for user issues

## Version Guidelines

- **Patch** (1.0.0 → 1.0.1): Bug fixes, typos
- **Minor** (1.0.0 → 1.1.0): New features, backwards compatible
- **Major** (1.0.0 → 2.0.0): Breaking changes

Remember: Once published, you cannot unpublish after 24 hours!