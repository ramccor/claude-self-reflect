#!/usr/bin/env python3
"""Test memory decay implementation without modifying existing data."""

import asyncio
import json
from datetime import datetime, timedelta
from qdrant_client import QdrantClient
from qdrant_client.models import *
import numpy as np

class DecayTester:
    def __init__(self):
        self.client = QdrantClient(url="http://localhost:6333")
        self.test_collection = "test_decay_collection"
        
    async def create_test_collection(self):
        """Create test collection with synthetic timestamps."""
        print("🧪 Creating test collection with synthetic timestamps...")
        
        # Sample from existing collections
        voyage_collections = [c.name for c in self.client.get_collections().collections 
                            if c.name.endswith('_voyage')]
        
        # Get sample points
        sample_points = []
        for collection in voyage_collections[:3]:  # First 3 collections
            result = self.client.scroll(
                collection_name=collection,
                limit=20,
                with_payload=True,
                with_vectors=True
            )
            sample_points.extend(result[0])
            
        # Create test collection
        if self.test_collection in [c.name for c in self.client.get_collections().collections]:
            self.client.delete_collection(self.test_collection)
            
        self.client.create_collection(
            collection_name=self.test_collection,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
        )
        
        # Insert with synthetic timestamps
        points_with_timestamps = []
        for i, point in enumerate(sample_points[:100]):
            # Spread timestamps over past year
            days_ago = (i / len(sample_points)) * 365
            timestamp = (datetime.now() - timedelta(days=days_ago)).isoformat()
            
            new_payload = point.payload.copy() if point.payload else {}
            new_payload["created_at"] = timestamp
            new_payload["test_age_days"] = days_ago
            
            points_with_timestamps.append(
                PointStruct(
                    id=i,
                    vector=point.vector,
                    payload=new_payload
                )
            )
            
        self.client.upsert(
            collection_name=self.test_collection,
            points=points_with_timestamps
        )
        
        print(f"✅ Created test collection with {len(points_with_timestamps)} points")
        
    async def test_decay_search(self, query_text="debugging React hooks"):
        """Compare search results with and without decay."""
        print(f"\n🔍 Testing search: '{query_text}'")
        
        # Get query vector (mock - in reality would use embedding service)
        query_vector = np.random.rand(1024).tolist()
        
        # Search WITHOUT decay
        results_no_decay = self.client.search(
            collection_name=self.test_collection,
            query_vector=query_vector,
            limit=10,
            with_payload=True
        )
        
        # Search WITH decay using Qdrant's formula query
        results_with_decay = self.client.query_points(
            collection_name=self.test_collection,
            prefetch=[
                Prefetch(
                    query=query_vector,
                    limit=50  # Get more candidates for decay filtering
                )
            ],
            query=FormulaQuery(
                formula=SumExpression(
                    sum=[
                        # Original score
                        "$score",
                        # Decay bonus (positive to boost recent items)
                        MultExpression(
                            mult=[
                                0.3,  # FIXED: Positive decay weight
                                ExpDecayExpression(
                                    exp_decay=DecayParamsExpression(
                                        # Age in days from payload
                                        x="test_age_days",
                                        target=0,  # Most recent
                                        scale=90   # 90-day half-life
                                    )
                                )
                            ]
                        )
                    ]
                )
            ),
            limit=10
        )
        
        # Analyze differences
        print("\n📊 Results Comparison:")
        print("Without Decay | With Decay")
        print("-" * 50)
        
        for i in range(min(10, len(results_no_decay), len(results_with_decay.points))):
            no_decay = results_no_decay[i] if i < len(results_no_decay) else None
            with_decay = results_with_decay.points[i] if i < len(results_with_decay.points) else None
            
            if no_decay and with_decay:
                age_no = no_decay.payload.get("test_age_days", 0)
                age_with = with_decay.payload.get("test_age_days", 0)
                print(f"#{i+1}: {age_no:.0f} days old | {age_with:.0f} days old")
                
        # Calculate metrics
        avg_age_no_decay = np.mean([r.payload.get("test_age_days", 0) for r in results_no_decay[:5]])
        avg_age_with_decay = np.mean([p.payload.get("test_age_days", 0) for p in results_with_decay.points[:5]])
        
        print(f"\n📈 Metrics:")
        print(f"Average age (top 5) without decay: {avg_age_no_decay:.1f} days")
        print(f"Average age (top 5) with decay: {avg_age_with_decay:.1f} days")
        print(f"Recency improvement: {(avg_age_no_decay - avg_age_with_decay) / avg_age_no_decay * 100:.1f}%")
        
        return {
            "query": query_text,
            "avg_age_no_decay": avg_age_no_decay,
            "avg_age_with_decay": avg_age_with_decay,
            "recency_improvement": (avg_age_no_decay - avg_age_with_decay) / avg_age_no_decay * 100
        }

async def main():
    tester = DecayTester()
    
    # Create test environment
    await tester.create_test_collection()
    
    # Test multiple queries
    queries = [
        "debugging React hooks",
        "database connection error",
        "authentication implementation",
        "performance optimization"
    ]
    
    results = []
    for query in queries:
        result = await tester.test_decay_search(query)
        results.append(result)
        
    # Summary
    print("\n🎯 Overall Results:")
    avg_improvement = np.mean([r["recency_improvement"] for r in results])
    print(f"Average recency improvement across all queries: {avg_improvement:.1f}%")
    print("\n✅ Memory decay testing complete!")
    print("ℹ️  No production data was modified during this test.")

if __name__ == "__main__":
    asyncio.run(main())