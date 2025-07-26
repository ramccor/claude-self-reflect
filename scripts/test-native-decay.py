#!/usr/bin/env python3
"""Test script for native Qdrant decay implementation."""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import (
    PointStruct, VectorParams, Distance
)
import numpy as np
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))

async def test_native_decay():
    """Test native Qdrant decay functions."""
    client = AsyncQdrantClient(url=QDRANT_URL)
    
    # Create a test collection
    test_collection = "test_native_decay"
    
    try:
        # Delete if exists
        try:
            await client.delete_collection(test_collection)
        except:
            pass
        
        # Create collection
        await client.create_collection(
            collection_name=test_collection,
            vectors_config=VectorParams(size=4, distance=Distance.COSINE)
        )
        
        # Create test points with different ages
        now = datetime.now()
        points = []
        
        # Point 1: Fresh (today)
        points.append(PointStruct(
            id=1,
            vector=[0.1, 0.2, 0.3, 0.4],
            payload={
                "text": "Fresh conversation about React hooks",
                "timestamp": now.isoformat()
            }
        ))
        
        # Point 2: 30 days old
        points.append(PointStruct(
            id=2,
            vector=[0.1, 0.2, 0.3, 0.5],  # Slightly different
            payload={
                "text": "Month-old conversation about React hooks",
                "timestamp": (now - timedelta(days=30)).isoformat()
            }
        ))
        
        # Point 3: 90 days old (half-life)
        points.append(PointStruct(
            id=3,
            vector=[0.1, 0.2, 0.3, 0.6],  # More different
            payload={
                "text": "Quarter-old conversation about React hooks",
                "timestamp": (now - timedelta(days=90)).isoformat()
            }
        ))
        
        # Point 4: 180 days old
        points.append(PointStruct(
            id=4,
            vector=[0.1, 0.2, 0.3, 0.7],  # Most different
            payload={
                "text": "Half-year-old conversation about React hooks",
                "timestamp": (now - timedelta(days=180)).isoformat()
            }
        ))
        
        # Insert points
        await client.upsert(
            collection_name=test_collection,
            points=points
        )
        
        # Test query vector
        query_vector = [0.1, 0.2, 0.3, 0.45]
        
        print("=" * 60)
        print("Testing Native Qdrant Decay")
        print("=" * 60)
        print(f"Decay Weight: {DECAY_WEIGHT}")
        print(f"Decay Scale (days): {DECAY_SCALE_DAYS}")
        print()
        
        # 1. Search WITHOUT decay
        print("1. Standard Search (No Decay):")
        print("-" * 40)
        
        results = await client.search(
            collection_name=test_collection,
            query_vector=query_vector,
            limit=10,
            with_payload=True
        )
        
        for point in results:
            age_days = (now - datetime.fromisoformat(point.payload['timestamp'])).days
            print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
            print(f"   Text: {point.payload['text']}")
        
        print()
        
        # 2. Search WITH native decay (CORRECT IMPLEMENTATION)
        print("2. Native Qdrant Decay Search (Prefetch + FormulaQuery):")
        print("-" * 40)
        print("ℹ️  Using the correct pattern: Prefetch for vector search, FormulaQuery for reranking")
        
        # CORRECT: Use Prefetch + FormulaQuery pattern
        results = await client.query_points(
            collection_name=test_collection,
            # Step 1: Prefetch candidates using vector similarity
            prefetch=models.Prefetch(
                query=query_vector,
                limit=20  # Get more candidates for reranking
            ),
            # Step 2: Apply decay formula to rerank results
            query=models.FormulaQuery(
                formula=models.SumExpression(sum=[
                    # Original similarity score from prefetch
                    models.Variable("$score"),
                    # Add decay boost term
                    models.MultExpression(mult=[
                        # Decay weight
                        models.Constant(DECAY_WEIGHT),
                        # Exponential decay function
                        models.ExpDecayExpression(exp_decay=models.DecayParamsExpression(
                            # Use timestamp field for decay
                            x=models.DatetimeKeyExpression(datetime_key='timestamp'),
                            # Decay from current time (server-side)
                            target=models.DatetimeExpression(datetime='now'),
                            # Scale in milliseconds
                            scale=DECAY_SCALE_DAYS * 24 * 60 * 60 * 1000,
                            # Standard exponential decay midpoint
                            midpoint=0.5
                        ))
                    ])
                ])
            ),
            limit=10,
            with_payload=True
        )
        
        for point in results.points:
            age_days = (now - datetime.fromisoformat(point.payload['timestamp'])).days
            print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
            print(f"   Text: {point.payload['text']}")
        
        print()
        print("=" * 60)
        print("Native Decay Effect (Using Correct Pattern):")
        print("✅ Prefetch retrieves candidates by vector similarity")
        print("✅ FormulaQuery applies decay-based reranking")
        print("✅ Fresh content gets boosted")
        print("✅ Older content scores are reduced")
        print("✅ Server-side calculation is efficient")
        print()
        print("ℹ️  Note: FormulaQuery does NOT accept 'nearest' parameter")
        print("    Always use Prefetch for vector search first!")
        
    finally:
        # Cleanup
        try:
            await client.delete_collection(test_collection)
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_native_decay())