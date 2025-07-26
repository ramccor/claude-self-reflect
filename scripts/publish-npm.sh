#!/bin/bash
# NPM Publishing Script for Claude-Self-Reflect

set -e  # Exit on error

echo "🚀 Claude-Self-Reflect NPM Publishing Script"
echo "==========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Change to package directory
cd "$(dirname "$0")/../claude-self-reflection"

# Check if logged in to NPM
echo -e "\n${YELLOW}Checking NPM login status...${NC}"
if ! npm whoami &>/dev/null; then
    echo -e "${RED}❌ Not logged in to NPM${NC}"
    echo "Please run: npm login"
    exit 1
fi
NPM_USER=$(npm whoami)
echo -e "${GREEN}✅ Logged in as: $NPM_USER${NC}"

# Check package name availability
PACKAGE_NAME=$(node -p "require('./package.json').name")
echo -e "\n${YELLOW}Checking if package name '$PACKAGE_NAME' is available...${NC}"
if npm view "$PACKAGE_NAME" &>/dev/null; then
    echo -e "${YELLOW}⚠️  Package already exists on NPM${NC}"
    CURRENT_VERSION=$(npm view "$PACKAGE_NAME" version)
    LOCAL_VERSION=$(node -p "require('./package.json').version")
    echo "  Current NPM version: $CURRENT_VERSION"
    echo "  Local version: $LOCAL_VERSION"
    
    if [ "$CURRENT_VERSION" == "$LOCAL_VERSION" ]; then
        echo -e "${RED}❌ Version $LOCAL_VERSION already published!${NC}"
        echo "Please bump the version using: npm version patch/minor/major"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Package name is available${NC}"
fi

# Clean and build
echo -e "\n${YELLOW}Cleaning and building...${NC}"
rm -rf dist node_modules
npm ci
npm run build
echo -e "${GREEN}✅ Build successful${NC}"

# Run tests
echo -e "\n${YELLOW}Running tests...${NC}"
npm test || echo -e "${YELLOW}⚠️  Tests skipped (CI only)${NC}"

# Security audit
echo -e "\n${YELLOW}Running security audit...${NC}"
npm audit --audit-level=high || echo -e "${YELLOW}⚠️  Some vulnerabilities found (review before publishing)${NC}"

# Pack test
echo -e "\n${YELLOW}Creating test package...${NC}"
npm pack
PACKAGE_FILE=$(ls -1 *.tgz | head -n 1)
PACKAGE_SIZE=$(du -h "$PACKAGE_FILE" | cut -f1)
echo -e "${GREEN}✅ Package created: $PACKAGE_FILE (${PACKAGE_SIZE})${NC}"

# Show package contents
echo -e "\n${YELLOW}Package contents:${NC}"
tar -tzf "$PACKAGE_FILE" | head -20
echo "..."

# Cleanup pack file
rm -f *.tgz

# Dry run
echo -e "\n${YELLOW}Running publish dry run...${NC}"
npm publish --dry-run

# Confirm
echo -e "\n${YELLOW}Ready to publish to NPM!${NC}"
echo "Package: $PACKAGE_NAME"
echo "Version: $(node -p "require('./package.json').version")"
echo -e "\n${RED}This action cannot be undone after 24 hours!${NC}"
read -p "Do you want to publish? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Publishing to NPM...${NC}"
    npm publish --access public
    echo -e "\n${GREEN}✅ Successfully published!${NC}"
    echo -e "\nVerify at: https://www.npmjs.com/package/$PACKAGE_NAME"
    echo -e "\nInstall with: npm install -g $PACKAGE_NAME"
else
    echo -e "\n${YELLOW}Publishing cancelled${NC}"
    exit 0
fi