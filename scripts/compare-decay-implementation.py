#!/usr/bin/env python3
"""Compare client-side vs native decay implementation performance."""

import asyncio
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import numpy as np
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))

async def compare_decay_approaches():
    """Compare client-side and native decay approaches."""
    client = AsyncQdrantClient(url=QDRANT_URL)
    
    # Create a test collection
    test_collection = "test_decay_comparison"
    
    try:
        # Delete if exists
        try:
            await client.delete_collection(test_collection)
        except:
            pass
        
        # Create collection
        await client.create_collection(
            collection_name=test_collection,
            vectors_config=VectorParams(size=128, distance=Distance.COSINE)
        )
        
        # Create test points with different ages
        now = datetime.now()
        points = []
        
        # Generate 1000 points with varying ages
        for i in range(1000):
            age_days = i % 365  # Ages from 0 to 364 days
            timestamp = now - timedelta(days=age_days)
            
            # Random vector
            vector = np.random.randn(128).tolist()
            
            points.append(PointStruct(
                id=i,
                vector=vector,
                payload={
                    "text": f"Test point {i} - {age_days} days old",
                    "timestamp": timestamp.isoformat(),
                    "age_days": age_days
                }
            ))
        
        # Insert points in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            await client.upsert(
                collection_name=test_collection,
                points=batch
            )
        
        print(f"Created {len(points)} test points")
        
        # Test query vector
        query_vector = np.random.randn(128).tolist()
        
        print("\n" + "=" * 60)
        print("Decay Performance Comparison")
        print("=" * 60)
        print(f"Collection: {test_collection}")
        print(f"Points: {len(points)}")
        print(f"Decay Weight: {DECAY_WEIGHT}")
        print(f"Decay Scale (days): {DECAY_SCALE_DAYS}")
        print()
        
        # 1. Client-side decay
        print("1. Client-Side Decay Implementation:")
        print("-" * 40)
        
        start_time = time.time()
        
        # Search without score threshold to get all candidates
        results = await client.search(
            collection_name=test_collection,
            query_vector=query_vector,
            limit=300,  # Get more candidates for decay filtering
            with_payload=True
        )
        
        # Apply decay scoring manually
        scale_ms = DECAY_SCALE_DAYS * 24 * 60 * 60 * 1000
        decay_results = []
        
        for point in results:
            timestamp_str = point.payload.get('timestamp')
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                age_ms = (now - timestamp).total_seconds() * 1000
                
                # Calculate decay factor
                decay_factor = np.exp(-age_ms / scale_ms)
                
                # Apply decay formula
                adjusted_score = point.score + (DECAY_WEIGHT * decay_factor)
                decay_results.append((adjusted_score, point))
            else:
                decay_results.append((point.score, point))
        
        # Sort by adjusted score and take top results
        decay_results.sort(key=lambda x: x[0], reverse=True)
        top_results = decay_results[:10]
        
        client_side_time = time.time() - start_time
        
        print(f"Time taken: {client_side_time:.3f} seconds")
        print("\nTop 5 results:")
        for i, (score, point) in enumerate(top_results[:5]):
            age_days = point.payload.get('age_days', 'unknown')
            print(f"  {i+1}. Score: {score:.4f}, Age: {age_days} days, ID: {point.id}")
        
        print()
        
        # 2. Native decay (if supported)
        print("2. Native Qdrant Decay Implementation:")
        print("-" * 40)
        print("Status: Not yet supported in Python SDK v1.15.0")
        print("Reason: FormulaQuery API not fully implemented")
        print()
        print("Future implementation will use:")
        print("- FormulaQuery with SumExpression")
        print("- ExpDecayExpression for time-based decay")
        print("- Server-side calculation for better performance")
        print()
        
        # Performance comparison summary
        print("=" * 60)
        print("Summary:")
        print("-" * 60)
        print(f"Client-side decay time: {client_side_time:.3f} seconds")
        print("Native decay time: N/A (pending SDK support)")
        print()
        print("Expected benefits of native decay:")
        print("- Server-side calculation reduces data transfer")
        print("- No need to fetch extra candidates")
        print("- Better integration with score thresholds")
        print("- Improved performance for large datasets")
        
    finally:
        # Cleanup
        try:
            await client.delete_collection(test_collection)
        except:
            pass

if __name__ == "__main__":
    asyncio.run(compare_decay_approaches())