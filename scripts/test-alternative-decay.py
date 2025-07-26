#!/usr/bin/env python3
"""Test script for alternative Qdrant decay implementations."""

import asyncio
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import (
    PointStruct, VectorParams, Distance,
    Filter, FieldCondition, Range,
    Prefetch, FormulaQuery, FusionQuery, Fusion
)
import numpy as np
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))

async def test_alternative_decay_approaches():
    """Test alternative approaches to implement memory decay in Qdrant."""
    client = AsyncQdrantClient(url=QDRANT_URL)
    
    # Create a test collection
    test_collection = "test_alternative_decay"
    
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
                "timestamp": now.isoformat(),
                "age_days": 0
            }
        ))
        
        # Point 2: 30 days old
        points.append(PointStruct(
            id=2,
            vector=[0.1, 0.2, 0.3, 0.5],  # Slightly different
            payload={
                "text": "Month-old conversation about React hooks",
                "timestamp": (now - timedelta(days=30)).isoformat(),
                "age_days": 30
            }
        ))
        
        # Point 3: 90 days old (half-life)
        points.append(PointStruct(
            id=3,
            vector=[0.1, 0.2, 0.3, 0.6],  # More different
            payload={
                "text": "Quarter-old conversation about React hooks",
                "timestamp": (now - timedelta(days=90)).isoformat(),
                "age_days": 90
            }
        ))
        
        # Point 4: 180 days old
        points.append(PointStruct(
            id=4,
            vector=[0.1, 0.2, 0.3, 0.7],  # Most different
            payload={
                "text": "Half-year-old conversation about React hooks",
                "timestamp": (now - timedelta(days=180)).isoformat(),
                "age_days": 180
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
        print("Testing Alternative Decay Approaches")
        print("=" * 60)
        print(f"Decay Weight: {DECAY_WEIGHT}")
        print(f"Decay Scale (days): {DECAY_SCALE_DAYS}")
        print()
        
        # Approach 1: Standard Search (Baseline)
        print("1. Standard Search (No Decay):")
        print("-" * 40)
        
        start_time = time.time()
        results = await client.search(
            collection_name=test_collection,
            query_vector=query_vector,
            limit=10,
            with_payload=True
        )
        baseline_time = time.time() - start_time
        
        for point in results:
            age_days = (now - datetime.fromisoformat(point.payload['timestamp'])).days
            print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
            print(f"   Text: {point.payload['text']}")
        
        print(f"\nTime: {baseline_time:.3f}s")
        print()
        
        # Approach 2: Prefetch + FormulaQuery (Correct Native Pattern)
        print("2. Prefetch + FormulaQuery Pattern:")
        print("-" * 40)
        
        try:
            start_time = time.time()
            # First prefetch to get candidates
            results = await client.query_points(
                collection_name=test_collection,
                prefetch=Prefetch(
                    query=query_vector,
                    limit=100,  # Get more candidates for re-scoring
                ),
                # Then apply formula for re-scoring
                query=FormulaQuery(
                    formula={
                        "sum": [
                            {"variable": "$score"},
                            {
                                "mult": [
                                    DECAY_WEIGHT,
                                    {
                                        "exp": {
                                            "div": [
                                                {"neg": {"datetime_key": "age_days"}},
                                                DECAY_SCALE_DAYS
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ),
                limit=10,
                with_payload=True
            )
            prefetch_time = time.time() - start_time
            
            for point in results.points:
                age_days = (now - datetime.fromisoformat(point.payload['timestamp'])).days
                print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
                print(f"   Text: {point.payload['text']}")
            
            print(f"\nTime: {prefetch_time:.3f}s (overhead: {prefetch_time - baseline_time:.3f}s)")
        except Exception as e:
            print(f"Error with prefetch approach: {e}")
        
        print()
        
        # Approach 3: Payload-Based Filtering (Time Window)
        print("3. Payload-Based Time Window Filtering:")
        print("-" * 40)
        
        start_time = time.time()
        # Only search points from last 60 days
        cutoff_date = now - timedelta(days=60)
        
        results = await client.search(
            collection_name=test_collection,
            query_vector=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="timestamp",
                        range=Range(
                            gte=cutoff_date.isoformat()
                        )
                    )
                ]
            ),
            limit=10,
            with_payload=True
        )
        filter_time = time.time() - start_time
        
        for point in results:
            age_days = (now - datetime.fromisoformat(point.payload['timestamp'])).days
            print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
            print(f"   Text: {point.payload['text']}")
        
        print(f"\nTime: {filter_time:.3f}s (overhead: {filter_time - baseline_time:.3f}s)")
        print()
        
        # Approach 4: Two-Stage Search with Client-Side Decay
        print("4. Two-Stage Search + Client-Side Decay:")
        print("-" * 40)
        
        start_time = time.time()
        # Stage 1: Get more candidates than needed
        candidates = await client.search(
            collection_name=test_collection,
            query_vector=query_vector,
            limit=50,  # Get extra candidates
            with_payload=True
        )
        
        # Stage 2: Apply decay scoring client-side
        decay_results = []
        for point in candidates:
            age_days = (now - datetime.fromisoformat(point.payload['timestamp'])).days
            decay_factor = np.exp(-age_days / DECAY_SCALE_DAYS)
            adjusted_score = point.score * (1 - DECAY_WEIGHT) + decay_factor * DECAY_WEIGHT
            decay_results.append({
                'id': point.id,
                'score': point.score,
                'adjusted_score': adjusted_score,
                'age_days': age_days,
                'payload': point.payload
            })
        
        # Sort by adjusted score and take top results
        decay_results.sort(key=lambda x: x['adjusted_score'], reverse=True)
        two_stage_time = time.time() - start_time
        
        for result in decay_results[:10]:
            print(f"ID: {result['id']}, Original: {result['score']:.4f}, "
                  f"Adjusted: {result['adjusted_score']:.4f}, Age: {result['age_days']} days")
            print(f"   Text: {result['payload']['text']}")
        
        print(f"\nTime: {two_stage_time:.3f}s (overhead: {two_stage_time - baseline_time:.3f}s)")
        print()
        
        # Approach 5: Hybrid Search with Time-Based Boosting
        print("5. Hybrid Search with Fusion:")
        print("-" * 40)
        
        try:
            start_time = time.time()
            # Create multiple prefetch queries with different time windows
            results = await client.query_points(
                collection_name=test_collection,
                prefetch=[
                    # Fresh content (last 30 days) with higher weight
                    Prefetch(
                        query=query_vector,
                        filter=Filter(
                            must=[
                                FieldCondition(
                                    key="timestamp",
                                    range=Range(
                                        gte=(now - timedelta(days=30)).isoformat()
                                    )
                                )
                            ]
                        ),
                        limit=10
                    ),
                    # Older content (30-90 days) with lower weight
                    Prefetch(
                        query=query_vector,
                        filter=Filter(
                            must=[
                                FieldCondition(
                                    key="timestamp",
                                    range=Range(
                                        gte=(now - timedelta(days=90)).isoformat(),
                                        lt=(now - timedelta(days=30)).isoformat()
                                    )
                                )
                            ]
                        ),
                        limit=10
                    )
                ],
                query=FusionQuery(
                    fusion=Fusion.RRF  # Reciprocal Rank Fusion
                ),
                limit=10,
                with_payload=True
            )
            fusion_time = time.time() - start_time
            
            for point in results.points:
                age_days = (now - datetime.fromisoformat(point.payload['timestamp'])).days
                print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
                print(f"   Text: {point.payload['text']}")
            
            print(f"\nTime: {fusion_time:.3f}s (overhead: {fusion_time - baseline_time:.3f}s)")
        except Exception as e:
            print(f"Error with fusion approach: {e}")
        
        print()
        
        # Summary
        print("=" * 60)
        print("Summary of Alternative Approaches:")
        print("1. Prefetch + FormulaQuery: Native Qdrant pattern for custom scoring")
        print("2. Time Window Filtering: Simple and efficient for hard cutoffs")
        print("3. Two-Stage + Client Decay: Most flexible, minimal overhead")
        print("4. Hybrid Fusion: Good for combining multiple time-based strategies")
        print()
        print("Recommendation: Use Two-Stage + Client Decay for best flexibility")
        print("and compatibility without SDK limitations.")
        
    finally:
        # Cleanup
        try:
            await client.delete_collection(test_collection)
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_alternative_decay_approaches())