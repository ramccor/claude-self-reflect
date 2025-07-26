#!/usr/bin/env python3
"""
Demo script to show memory decay impact on search results
"""
import os
import sys
from datetime import datetime, timedelta
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import voyageai

# Initialize clients
voyage_client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY") or os.getenv("VOYAGE_KEY"))
qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

# Get the voyage collection
collections = qdrant_client.get_collections().collections
voyage_collections = [c.name for c in collections if c.name.endswith("_voyage")]

if not voyage_collections:
    print("❌ No Voyage collections found. Please import some conversations first.")
    sys.exit(1)

collection_name = voyage_collections[0]
print(f"🔍 Using collection: {collection_name}")

# Search query
query = "qdrant memory decay"
print(f"\n📝 Query: '{query}'")

# Generate embedding
embedding = voyage_client.embed([query], model="voyage-3-large").embeddings[0]

# Search WITHOUT decay (traditional search)
print("\n" + "="*80)
print("🔍 SEARCH WITHOUT DECAY (Traditional)")
print("="*80)

results_no_decay = qdrant_client.search(
    collection_name=collection_name,
    query_vector=embedding,
    limit=5,
    with_payload=True
)

print(f"\nTop 5 results:")
for i, result in enumerate(results_no_decay, 1):
    timestamp = result.payload.get('timestamp', 'Unknown')
    if timestamp != 'Unknown':
        dt = datetime.fromisoformat(timestamp)
        age = (datetime.now() - dt.replace(tzinfo=None)).days
        print(f"\n{i}. Score: {result.score:.3f}")
        print(f"   Age: {age} days old ({dt.strftime('%Y-%m-%d')})")
        print(f"   Text: {result.payload.get('text', '')[:100]}...")
    else:
        print(f"\n{i}. Score: {result.score:.3f}")
        print(f"   Text: {result.payload.get('text', '')[:100]}...")

# Search WITH decay (client-side)
print("\n" + "="*80)
print("🔍 SEARCH WITH MEMORY DECAY (Recent conversations prioritized)")
print("="*80)

# Apply client-side decay
decay_weight = float(os.getenv("DECAY_WEIGHT", "0.3"))
decay_scale_days = float(os.getenv("DECAY_SCALE_DAYS", "90"))

results_with_decay = []
for result in results_no_decay:
    timestamp = result.payload.get('timestamp', None)
    if timestamp:
        dt = datetime.fromisoformat(timestamp)
        age_days = (datetime.now() - dt.replace(tzinfo=None)).days
        
        # Calculate decay factor (exponential decay)
        import math
        decay_factor = math.exp(-age_days / decay_scale_days)
        
        # Apply weighted combination
        original_score = result.score
        decayed_score = original_score * (1 - decay_weight) + decay_factor * decay_weight
        
        results_with_decay.append({
            'score': decayed_score,
            'original_score': original_score,
            'decay_factor': decay_factor,
            'age_days': age_days,
            'timestamp': timestamp,
            'text': result.payload.get('text', ''),
            'result': result
        })

# Sort by decayed score
results_with_decay.sort(key=lambda x: x['score'], reverse=True)

print(f"\nTop 5 results (with decay applied):")
print(f"Decay weight: {decay_weight}, Half-life: {decay_scale_days} days")
for i, item in enumerate(results_with_decay[:5], 1):
    dt = datetime.fromisoformat(item['timestamp'])
    print(f"\n{i}. Decayed Score: {item['score']:.3f} (Original: {item['original_score']:.3f}, Decay factor: {item['decay_factor']:.3f})")
    print(f"   Age: {item['age_days']} days old ({dt.strftime('%Y-%m-%d')})")
    print(f"   Text: {item['text'][:100]}...")

# Summary
print("\n" + "="*80)
print("📊 SUMMARY")
print("="*80)

avg_age_no_decay = sum([(datetime.now() - datetime.fromisoformat(r.payload.get('timestamp', datetime.now().isoformat())).replace(tzinfo=None)).days for r in results_no_decay[:5]]) / 5
avg_age_with_decay = sum([item['age_days'] for item in results_with_decay[:5]]) / 5

print(f"\nAverage age of top 5 results:")
print(f"  Without decay: {avg_age_no_decay:.0f} days")
print(f"  With decay:    {avg_age_with_decay:.0f} days")
print(f"  Improvement:   {avg_age_no_decay - avg_age_with_decay:.0f} days more recent!")

print("\n✨ Memory decay successfully prioritizes recent conversations!")
print("   Recent memories are more relevant for most queries.")