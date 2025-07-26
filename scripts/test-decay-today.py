#!/usr/bin/env python3
"""Test decay functionality with today's conversation about memory decay."""

import os
import sys
from datetime import datetime
from qdrant_client import QdrantClient
import voyageai

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", os.getenv("VOYAGE_KEY"))

if not VOYAGE_API_KEY:
    print("Error: VOYAGE_API_KEY or VOYAGE_KEY environment variable not set")
    sys.exit(1)

# Initialize clients
client = QdrantClient(url=QDRANT_URL)
voyage = voyageai.Client(api_key=VOYAGE_API_KEY)

def test_today_conversation():
    """Test searching for today's memory decay discussion."""
    collection_name = "conv_b2795adc_voyage"  # memento-stack collection
    
    # Test query about today's discussion
    query = "Qdrant built-in decay functions exp_decay lin_decay gauss_decay memory decay philosophy"
    
    print(f"🔍 Testing search for today's memory decay discussion")
    print(f"📍 Collection: {collection_name}")
    print(f"🔎 Query: {query[:80]}...")
    
    # Generate embedding
    print("\n📊 Generating embedding...")
    embedding = voyage.embed(query, model="voyage-3-large", input_type="query").embeddings[0]
    
    # Search WITHOUT decay
    print("\n1️⃣ Search without decay:")
    results_no_decay = client.search(
        collection_name=collection_name,
        query_vector=embedding,
        limit=5,
        with_payload=True
    )
    
    for i, result in enumerate(results_no_decay):
        timestamp = result.payload.get("timestamp", 0)
        age_hours = (datetime.now().timestamp() - timestamp) / 3600
        text_preview = result.payload.get("text", "")[:150].replace("\n", " ")
        print(f"\n  #{i+1} Score: {result.score:.3f} | Age: {age_hours:.1f} hours")
        print(f"      {text_preview}...")
    
    # Search WITH decay using Qdrant's formula
    print("\n\n2️⃣ Search with decay (90-day half-life):")
    from qdrant_client.models import (
        Prefetch, ScoredPoint, FormulaQuery, SumExpression, 
        MultExpression, ExpDecayExpression, DecayParamsExpression
    )
    
    results_with_decay = client.query_points(
        collection_name=collection_name,
        prefetch=[
            Prefetch(
                query=embedding,
                limit=20  # Get more candidates
            )
        ],
        query=FormulaQuery(
            formula=SumExpression(
                sum=[
                    "$score",  # Original similarity score
                    MultExpression(
                        mult=[
                            -0.3,  # Decay weight (negative to penalize old content)
                            ExpDecayExpression(
                                exp_decay=DecayParamsExpression(
                                    x="timestamp",
                                    target=int(datetime.now().timestamp()),  # Current time
                                    scale=7776000  # 90 days in seconds
                                )
                            )
                        ]
                    )
                ]
            )
        ),
        limit=5
    ).points
    
    for i, result in enumerate(results_with_decay):
        timestamp = result.payload.get("timestamp", 0)
        age_hours = (datetime.now().timestamp() - timestamp) / 3600
        text_preview = result.payload.get("text", "")[:150].replace("\n", " ")
        print(f"\n  #{i+1} Score: {result.score:.3f} | Age: {age_hours:.1f} hours")
        print(f"      {text_preview}...")
    
    # Compare average ages
    avg_age_no_decay = sum((datetime.now().timestamp() - r.payload.get("timestamp", 0)) / 3600 
                           for r in results_no_decay[:3]) / 3
    avg_age_with_decay = sum((datetime.now().timestamp() - r.payload.get("timestamp", 0)) / 3600 
                             for r in results_with_decay[:3]) / 3
    
    print(f"\n📈 Summary:")
    print(f"   Average age (top 3) without decay: {avg_age_no_decay:.1f} hours")
    print(f"   Average age (top 3) with decay: {avg_age_with_decay:.1f} hours")
    print(f"   Recency improvement: {((avg_age_no_decay - avg_age_with_decay) / avg_age_no_decay * 100):.1f}%")
    
    # Check if today's conversation appears in top results
    today_found = False
    for result in results_with_decay[:3]:
        age_hours = (datetime.now().timestamp() - result.payload.get("timestamp", 0)) / 3600
        if age_hours < 6:  # Within last 6 hours
            today_found = True
            break
    
    print(f"\n✅ Today's conversation in top 3 results: {'Yes' if today_found else 'No'}")
    print("\n🎯 Memory decay is {'working correctly' if avg_age_with_decay < avg_age_no_decay else 'not improving recency'}!")

if __name__ == "__main__":
    test_today_conversation()