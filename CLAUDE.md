# Connectiva AI Project Guide for Claude

## Project Overview
Connectiva AI is a Shopify app built with Remix that integrates with n8n workflows for automation. The app helps merchants automate various e-commerce operations through AI-powered workflows.

## Critical Context

### 1. N8N Workflow Integration Patterns

**Common Issues:**
- **Webhook Authentication**: The app uses `X-N8N-Secret` header for webhook authentication. The secret must match between n8n environment variables and the app's `.env`
- **Workflow IDs**: Multiple workflow IDs are stored in environment variables (GENERAL_AUTOMATION_WORKFLOW_ID, PATTERN_DISCOVERY_WORKFLOW_ID, etc.)
- **API Endpoints**: Key n8n endpoints include `/api/n8n/active-shops`, `/api/n8n/trigger-workflow`

**Best Practices:**
```typescript
// Always verify webhook secret
const webhookSecret = request.headers.get("X-N8N-Secret");
if (webhookSecret !== process.env.N8N_WEBHOOK_SECRET) {
  return json({ error: "Unauthorized" }, { status: 401 });
}
```

### 2. Deployment Architecture

**Railway Deployment:**
- Services: `connectiva-app`, PostgreSQL, Redis, n8n
- Use `railway up --service connectiva-app` for deployment
- Check deployment status with `railway status`
- View logs with `railway logs`

**Environment Variables (Railway):**
```bash
# Critical for Railway
DATABASE_URL          # PostgreSQL connection
REDIS_URL            # Redis connection  
N8N_URL              # n8n instance URL
N8N_API_KEY          # n8n API authentication
N8N_WEBHOOK_SECRET   # Webhook security
```

**Local Development:**
```bash
# Start development server
npm run dev

# Common issues:
# - Port conflicts: Kill existing Vite servers before starting
# - Use ngrok or cloudflare tunnel for webhook testing
```

### 3. Database & Redis Connection Patterns

**Common Connection Issues:**
- **Redis reconnection loops**: Often caused by Railway Redis URL format issues
- **Database timeouts**: Use connection pooling and implement retry logic
- **Memory issues**: Monitor memory usage, especially in production

**Connection Monitoring Pattern:**
```typescript
// Always implement connection monitoring
export class ConnectionMonitor {
  async checkDatabase() {
    try {
      await prisma.$queryRaw`SELECT 1`;
      return { status: 'healthy' };
    } catch (error) {
      logger.error('Database connection failed', { error });
      return { status: 'unhealthy', error };
    }
  }
}
```

### 4. Project Structure

```
connectiva-ai/
├── app/
│   ├── routes/           # Remix routes (app.*.tsx pattern)
│   ├── services/         # Business logic services
│   │   ├── n8n/         # n8n integration
│   │   ├── ai/          # AI service integrations
│   │   └── shopify/     # Shopify API services
│   ├── components/       # React components
│   ├── utils/           # Utility functions
│   └── db.server.ts     # Database singleton
├── prisma/              # Database schema
└── public/              # Static assets
```

### 5. Key Integration Points

**Shopify Integration:**
- Uses `@shopify/shopify-app-remix` for authentication
- Session handling with `authenticate.admin(request)`
- Webhook handlers in `app/routes/webhooks.*.tsx`

**AI Services:**
- OpenAI integration for pattern analysis
- Anthropic Claude for advanced processing
- Voyage AI for embeddings

### 6. Common Debugging Scenarios

**When n8n workflows fail:**
1. Check webhook secret matching
2. Verify workflow IDs in environment
3. Test with curl: 
```bash
curl -X POST "https://your-app.railway.app/api/n8n/trigger-workflow" \
  -H "X-N8N-Secret: your-secret" \
  -H "Content-Type: application/json"
```

**When database connections fail:**
1. Check DATABASE_URL format
2. Verify Railway service is running
3. Test connection with: `npx prisma db pull`

**When Redis fails:**
1. Check REDIS_URL includes authentication
2. Monitor for connection cycling
3. Implement exponential backoff

### 7. Testing Approach

**Test Files Pattern:**
```javascript
// test-railway-connections.mjs
import { PrismaClient } from '@prisma/client';
import Redis from 'ioredis';

// Test all external connections
async function testConnections() {
  // Test PostgreSQL
  const prisma = new PrismaClient();
  await prisma.$queryRaw`SELECT 1`;
  
  // Test Redis
  const redis = new Redis(process.env.REDIS_URL);
  await redis.ping();
}
```

### 8. Performance Considerations

**Memory Management:**
- Monitor memory usage with health endpoints
- Implement garbage collection triggers
- Use streaming for large data processing

**Database Optimization:**
- Use Prisma query optimization
- Implement proper indexing
- Monitor slow queries in development

### 9. Environment Variables Reference

**Required for Development:**
```env
# Shopify (auto-populated by CLI)
SHOPIFY_APP_URL
SHOPIFY_API_KEY
SHOPIFY_API_SECRET

# Database
DATABASE_URL="postgresql://user:pass@localhost:5432/connectiva"
REDIS_URL="redis://localhost:6379"

# n8n Integration
N8N_URL="http://localhost:5678"
N8N_API_KEY="your-api-key"
N8N_WEBHOOK_SECRET="your-webhook-secret"

# Workflow IDs
GENERAL_AUTOMATION_WORKFLOW_ID="workflow-id"
PATTERN_DISCOVERY_WORKFLOW_ID="workflow-id"
```

### 10. Critical Commands

```bash
# Development
npm run dev                    # Start dev server
npm run shopify app dev       # Start with Shopify CLI

# Database
npx prisma migrate dev        # Run migrations
npx prisma studio            # Open database UI

# Deployment
railway up                   # Deploy to Railway
railway logs                # View deployment logs
railway run npm run build   # Build on Railway

# Debugging
node test-railway-connections.mjs  # Test all connections
npm run validate:env              # Check environment setup
```

### 11. Common Pitfalls to Avoid

1. **Don't hardcode workflow IDs** - Always use environment variables
2. **Don't skip webhook authentication** - Security is critical
3. **Don't ignore connection monitoring** - Implement health checks
4. **Don't deploy without testing connections** - Use test scripts
5. **Don't forget to handle n8n API errors** - Implement proper error boundaries

### 12. Quick Debugging Checklist

When something breaks:
- [ ] Check all environment variables are set
- [ ] Verify Railway services are running
- [ ] Test database and Redis connections
- [ ] Check n8n webhook secret matches
- [ ] Review recent deployment logs
- [ ] Test with local development first
- [ ] Check for port conflicts (3000, 5173)
- [ ] Verify Shopify tunnel is running for webhooks

## Session-Specific Notes

- Always test n8n integrations with actual webhook calls
- Monitor memory usage in production (Railway has limits)
- Use connection pooling for database stability
- Implement proper error logging for debugging
- Keep webhook endpoints lightweight