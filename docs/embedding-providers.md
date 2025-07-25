# Embedding Provider Guide

## Choose Your Embedding Provider

Embedding models convert your conversations into numbers that enable semantic search. Choose the option that best fits your needs:

### Voyage AI (Recommended)
- **200M tokens FREE** - covers most users completely  
- Best quality for conversation search
- Only $0.02/1M tokens after free tier
- [Get API key](https://dash.voyageai.com/)

**Why choose Voyage?** Purpose-built for retrieval tasks, massive free tier means most users never pay.

### Google Gemini (Free Alternative)
- **Completely FREE** (unlimited usage)
- Your data used to improve Google products  
- Good multilingual support
- [Get API key](https://ai.google.dev/gemini-api/docs)

**Why choose Gemini?** Best for users who want unlimited free usage and don't mind data sharing.

### Local Processing (Privacy First)
- **Completely FREE**, works offline
- No API keys, no data sharing
- Lower quality results, slower processing
- No setup required

**Why choose Local?** Perfect for privacy-focused users or those who want to avoid any external dependencies.

### OpenAI (If You Have Credits)
- No free tier
- $0.02/1M tokens (same as Voyage paid)  
- Good quality, established ecosystem
- [Get API key](https://platform.openai.com/api-keys)

**Why choose OpenAI?** If you already have OpenAI credits or prefer their ecosystem.

## Configuration

```bash
# Voyage AI (Recommended - 200M tokens FREE)
export VOYAGE_API_KEY="your-api-key"

# OR Google Gemini (Unlimited FREE)  
export GEMINI_API_KEY="your-api-key"

# OR OpenAI (No free tier)
export OPENAI_API_KEY="your-api-key"

# OR Local Processing (Always FREE)
export USE_LOCAL_EMBEDDINGS=true
```

## Cost Estimation

**Free Tiers:**
- Voyage AI: 200M tokens FREE, then $0.02 per 1M tokens
- Google Gemini: Unlimited FREE (data used for training)
- Local: Always FREE

**Paid Only:**
- OpenAI: $0.02 per 1M tokens (no free tier)

**Reality Check:** With 500 tokens per conversation chunk, 200M free tokens = ~400,000 conversation chunks. Most users never reach the paid tier.

## Custom Embedding Models

```bash
# Use OpenAI's latest model
EMBEDDING_MODEL=text-embedding-3-large

# Use Voyage's latest model  
EMBEDDING_MODEL=voyage-3

# Use a custom Hugging Face model
EMBEDDING_MODEL=intfloat/e5-large-v2
```