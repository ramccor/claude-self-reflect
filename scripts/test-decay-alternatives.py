#!/usr/bin/env python3
"""
Alternative approaches to implement memory decay in Qdrant.
This script demonstrates multiple methods that avoid the FormulaQuery(nearest=...) issue.
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import (
    PointStruct, VectorParams, Distance, Filter, FieldCondition, Range,
    Prefetch, FormulaQuery, SumExpression, MultExpression,
    ExpDecayExpression, DecayParamsExpression, GaussDecayExpression,
    DatetimeExpression, DatetimeKeyExpression, FusionQuery, Fusion
)
import numpy as np
from dotenv import load_dotenv
import time

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))

class DecayAlternatives:
    """Demonstrates various approaches to implement memory decay in Qdrant."""
    
    def __init__(self):
        self.client = AsyncQdrantClient(url=QDRANT_URL)
        self.test_collection = "test_decay_alternatives"
        
    async def setup_test_collection(self):
        """Create test collection with sample data."""
        # Delete if exists
        try:
            await self.client.delete_collection(self.test_collection)
        except:
            pass
        
        # Create collection
        await self.client.create_collection(
            collection_name=self.test_collection,
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
                "timestamp_ms": int(now.timestamp() * 1000),
                "age_days": 0,
                "topic": "react"
            }
        ))
        
        # Point 2: 30 days old
        old_30 = now - timedelta(days=30)
        points.append(PointStruct(
            id=2,
            vector=[0.1, 0.2, 0.3, 0.5],
            payload={
                "text": "Month-old conversation about React hooks",
                "timestamp": old_30.isoformat(),
                "timestamp_ms": int(old_30.timestamp() * 1000),
                "age_days": 30,
                "topic": "react"
            }
        ))
        
        # Point 3: 90 days old (half-life)
        old_90 = now - timedelta(days=90)
        points.append(PointStruct(
            id=3,
            vector=[0.1, 0.2, 0.3, 0.6],
            payload={
                "text": "Quarter-old conversation about React hooks",
                "timestamp": old_90.isoformat(),
                "timestamp_ms": int(old_90.timestamp() * 1000),
                "age_days": 90,
                "topic": "react"
            }
        ))
        
        # Point 4: 180 days old
        old_180 = now - timedelta(days=180)
        points.append(PointStruct(
            id=4,
            vector=[0.1, 0.2, 0.3, 0.7],
            payload={
                "text": "Half-year-old conversation about React hooks",
                "timestamp": old_180.isoformat(),
                "timestamp_ms": int(old_180.timestamp() * 1000),
                "age_days": 180,
                "topic": "react"
            }
        ))
        
        # Insert points
        await self.client.upsert(
            collection_name=self.test_collection,
            points=points
        )
        
        print("✅ Test collection created with 4 points of varying ages")
        
    async def approach_1_prefetch_with_formula(self):
        """Approach 1: Use Prefetch + FormulaQuery (correct pattern)."""
        print("\n" + "="*60)
        print("APPROACH 1: Prefetch + FormulaQuery Pattern")
        print("="*60)
        
        query_vector = [0.1, 0.2, 0.3, 0.45]
        
        try:
            # First, do a standard search to get baseline
            print("\nBaseline search (no decay):")
            response = await self.client.query_points(
                collection_name=self.test_collection,
                query=query_vector,
                limit=10,
                with_payload=True
            )
            baseline = response.points
            
            for point in baseline:
                age_days = point.payload.get('age_days', 'unknown')
                print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
            
            # Now implement decay with prefetch pattern
            print("\n✅ Decay search with Prefetch + FormulaQuery:")
            
            results = await self.client.query_points(
                collection_name=self.test_collection,
                prefetch=Prefetch(
                    query=query_vector,
                    limit=20  # Get more candidates for reranking
                ),
                query=FormulaQuery(
                    formula={
                        "sum": [
                            "$score",
                            {
                                "mult": [
                                    DECAY_WEIGHT,
                                    {
                                        "exp_decay": {
                                            "x": {"datetime_key": "timestamp"},
                                            "target": {"datetime": "now"},
                                            "scale": DECAY_SCALE_DAYS * 24 * 60 * 60 * 1000,
                                            "midpoint": 0.5
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
            
            print("Results with decay applied:")
            for point in results.points:
                age_days = point.payload.get('age_days', 'unknown')
                print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in Approach 1: {e}")
            return False
    
    async def approach_2_payload_filtering(self):
        """Approach 2: Use payload-based filtering to exclude old data."""
        print("\n" + "="*60)
        print("APPROACH 2: Payload-Based Filtering")
        print("="*60)
        
        query_vector = [0.1, 0.2, 0.3, 0.45]
        cutoff_date = datetime.now() - timedelta(days=60)
        
        print(f"Filtering out data older than {cutoff_date.strftime('%Y-%m-%d')}")
        
        # Search with time-based filter
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="age_days",
                        range=Range(
                            lte=60  # Filter for points less than 60 days old
                        )
                    )
                ]
            ),
            limit=10,
            with_payload=True
        )
        results = response.points
        
        print("\nResults (only recent data):")
        for point in results:
            age_days = point.payload.get('age_days', 'unknown')
            print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
        
        return True
    
    async def approach_3_client_side_reranking(self):
        """Approach 3: Client-side reranking with decay calculation."""
        print("\n" + "="*60)
        print("APPROACH 3: Client-Side Reranking")
        print("="*60)
        
        query_vector = [0.1, 0.2, 0.3, 0.45]
        
        # Get more results than needed
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            limit=20,  # Get extra for reranking
            with_payload=True
        )
        results = response.points
        
        print("Original scores:")
        for point in results[:4]:
            age_days = point.payload.get('age_days', 'unknown')
            print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
        
        # Apply decay client-side
        now = datetime.now()
        reranked = []
        
        for point in results:
            timestamp_str = point.payload.get('timestamp')
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str)
                age_days = (now - timestamp).days
                
                # Calculate exponential decay
                decay_factor = np.exp(-age_days / DECAY_SCALE_DAYS)
                
                # Apply decay to score
                decayed_score = point.score * (1 - DECAY_WEIGHT) + decay_factor * DECAY_WEIGHT
                
                reranked.append({
                    'id': point.id,
                    'original_score': point.score,
                    'decay_factor': decay_factor,
                    'decayed_score': decayed_score,
                    'age_days': age_days,
                    'payload': point.payload
                })
        
        # Sort by decayed score
        reranked.sort(key=lambda x: x['decayed_score'], reverse=True)
        
        print("\n✅ After client-side decay reranking:")
        for item in reranked[:4]:
            print(f"ID: {item['id']}, "
                  f"Original: {item['original_score']:.4f}, "
                  f"Decay: {item['decay_factor']:.4f}, "
                  f"Final: {item['decayed_score']:.4f}, "
                  f"Age: {item['age_days']} days")
        
        return True
    
    async def approach_4_hybrid_search_fusion(self):
        """Approach 4: Use hybrid search with fusion to combine vector and time relevance."""
        print("\n" + "="*60)
        print("APPROACH 4: Hybrid Search with Fusion")
        print("="*60)
        
        query_vector = [0.1, 0.2, 0.3, 0.45]
        
        # Create a second "time relevance" score based on age_days payload
        # This requires creating a custom scoring mechanism
        
        try:
            # Use fusion query to combine multiple prefetch results
            results = await self.client.query_points(
                collection_name=self.test_collection,
                prefetch=[
                    # Regular vector search
                    Prefetch(
                        query=query_vector,
                        limit=20
                    ),
                    # Filter for recent items (boost recent)
                    Prefetch(
                        query=query_vector,
                        filter=Filter(
                            must=[
                                FieldCondition(
                                    key="age_days",
                                    range=Range(lte=30)  # Last 30 days
                                )
                            ]
                        ),
                        limit=20
                    )
                ],
                query=FusionQuery(fusion=Fusion.RRF),  # Reciprocal Rank Fusion
                limit=10,
                with_payload=True
            )
            
            print("✅ Fusion results (recent items boosted):")
            for point in results.points:
                age_days = point.payload.get('age_days', 'unknown')
                print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in Approach 4: {e}")
            return False
    
    async def approach_5_score_threshold(self):
        """Approach 5: Use score_threshold with adjusted similarity calculation."""
        print("\n" + "="*60)
        print("APPROACH 5: Score Threshold with Time Windows")
        print("="*60)
        
        query_vector = [0.1, 0.2, 0.3, 0.45]
        
        # Search in time windows with different thresholds
        time_windows = [
            (0, 30, 0.5),      # Recent: lower threshold
            (31, 90, 0.7),     # Medium: medium threshold
            (91, 180, 0.9),    # Old: high threshold
        ]
        
        all_results = []
        
        for min_days, max_days, threshold in time_windows:
            print(f"\nSearching {min_days}-{max_days} days with threshold {threshold}")
            
            response = await self.client.query_points(
                collection_name=self.test_collection,
                query=query_vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="age_days",
                            range=Range(gte=min_days, lte=max_days)
                        )
                    ]
                ),
                score_threshold=threshold,
                limit=5,
                with_payload=True
            )
            results = response.points
            
            for point in results:
                age_days = point.payload.get('age_days', 'unknown')
                print(f"  ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
                all_results.append(point)
        
        # Sort combined results
        all_results.sort(key=lambda x: x.score, reverse=True)
        
        print("\n✅ Combined results from all time windows:")
        for point in all_results[:4]:
            age_days = point.payload.get('age_days', 'unknown')
            print(f"ID: {point.id}, Score: {point.score:.4f}, Age: {age_days} days")
        
        return True
    
    async def performance_comparison(self):
        """Compare performance of different approaches."""
        print("\n" + "="*60)
        print("PERFORMANCE COMPARISON")
        print("="*60)
        
        query_vector = [0.1, 0.2, 0.3, 0.45]
        iterations = 10
        
        # Baseline search
        start = time.time()
        for _ in range(iterations):
            await self.client.query_points(
                collection_name=self.test_collection,
                query=query_vector,
                limit=10
            )
        baseline_time = (time.time() - start) / iterations
        print(f"Baseline search: {baseline_time*1000:.2f}ms avg")
        
        # Client-side decay
        start = time.time()
        for _ in range(iterations):
            response = await self.client.query_points(
                collection_name=self.test_collection,
                query=query_vector,
                limit=20,
                with_payload=True
            )
            results = response.points
            # Simulate decay calculation
            now = datetime.now()
            for point in results:
                if point.payload.get('timestamp'):
                    timestamp = datetime.fromisoformat(point.payload['timestamp'])
                    age_days = (now - timestamp).days
                    decay_factor = np.exp(-age_days / DECAY_SCALE_DAYS)
                    decayed_score = point.score * (1 - DECAY_WEIGHT) + decay_factor * DECAY_WEIGHT
        client_decay_time = (time.time() - start) / iterations
        print(f"Client-side decay: {client_decay_time*1000:.2f}ms avg (+{(client_decay_time-baseline_time)*1000:.2f}ms)")
        
        # Payload filtering
        start = time.time()
        cutoff_date = datetime.now() - timedelta(days=60)
        for _ in range(iterations):
            await self.client.query_points(
                collection_name=self.test_collection,
                query=query_vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="age_days",
                            range=Range(lte=60)
                        )
                    ]
                ),
                limit=10
            )
        filter_time = (time.time() - start) / iterations
        print(f"Payload filtering: {filter_time*1000:.2f}ms avg (+{(filter_time-baseline_time)*1000:.2f}ms)")
    
    async def cleanup(self):
        """Clean up test collection."""
        try:
            await self.client.delete_collection(self.test_collection)
            print("\n✅ Test collection cleaned up")
        except:
            pass
    
    async def run_all(self):
        """Run all alternative approaches."""
        await self.setup_test_collection()
        
        approaches = [
            self.approach_1_prefetch_with_formula,
            self.approach_2_payload_filtering,
            self.approach_3_client_side_reranking,
            self.approach_4_hybrid_search_fusion,
            self.approach_5_score_threshold,
        ]
        
        results = []
        for approach in approaches:
            try:
                success = await approach()
                results.append((approach.__name__, success))
            except Exception as e:
                print(f"Error in {approach.__name__}: {e}")
                results.append((approach.__name__, False))
        
        await self.performance_comparison()
        
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        for name, success in results:
            status = "✅ Success" if success else "❌ Failed"
            print(f"{name}: {status}")
        
        print("\n📊 RECOMMENDATIONS:")
        print("1. Client-side reranking (Approach 3) - Most flexible, minimal overhead")
        print("2. Payload filtering (Approach 2) - Simple, good for hard cutoffs")
        print("3. Prefetch + Formula (Approach 1) - Native but requires correct pattern")
        print("4. Hybrid fusion (Approach 4) - Good for combining signals")
        print("5. Score thresholds (Approach 5) - Useful for quality control")
        
        await self.cleanup()

async def main():
    """Main entry point."""
    tester = DecayAlternatives()
    await tester.run_all()

if __name__ == "__main__":
    asyncio.run(main())