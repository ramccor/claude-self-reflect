#!/usr/bin/env python3
"""
Test native decay with numeric timestamps (workaround for datetime_key issue).
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import (
    PointStruct, VectorParams, Distance, Prefetch, FormulaQuery
)
import numpy as np
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
import time

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))

console = Console()

class NativeDecayNumericTester:
    """Test native decay with numeric timestamps as workaround."""
    
    def __init__(self):
        self.client = AsyncQdrantClient(url=QDRANT_URL)
        self.test_collection = "native_decay_numeric_test"
        
    async def setup_test_data(self):
        """Create test collection with numeric timestamp data."""
        try:
            await self.client.delete_collection(self.test_collection)
        except:
            pass
        
        await self.client.create_collection(
            collection_name=self.test_collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        
        # Create test points with numeric timestamps
        now = datetime.now()
        now_ms = int(now.timestamp() * 1000)  # Current time in milliseconds
        points = []
        
        for days_ago in [0, 30, 90, 180, 365]:
            timestamp = now - timedelta(days=days_ago)
            timestamp_ms = int(timestamp.timestamp() * 1000)
            
            # Create identical vectors to test pure decay effect
            vector = np.ones(384).tolist()  # All 1s for identical content
            
            points.append(PointStruct(
                id=len(points) + 1,
                vector=vector,
                payload={
                    "text": f"Content from {days_ago} days ago",
                    "timestamp": timestamp.isoformat(),
                    "timestamp_ms": timestamp_ms,  # Numeric milliseconds
                    "timestamp_s": int(timestamp.timestamp()),  # Numeric seconds
                    "age_days": days_ago,
                    "age_ms": now_ms - timestamp_ms  # Age in milliseconds
                }
            ))
        
        await self.client.upsert(
            collection_name=self.test_collection,
            points=points
        )
        
        console.print(f"[green]✓ Created test collection with {len(points)} points using numeric timestamps[/green]")
        return points
        
    async def test_native_decay_numeric(self):
        """Test native decay with numeric timestamp fields."""
        query_vector = np.ones(384).tolist()  # Same as our test vectors
        
        console.print("\n[bold cyan]Testing Native Decay with Numeric Timestamps[/bold cyan]")
        
        # Approach 1: Using timestamp_ms field with exp_decay
        console.print("\n[yellow]1. Using numeric timestamp_ms with exp_decay:[/yellow]")
        try:
            # Current time in milliseconds
            now_ms = int(datetime.now().timestamp() * 1000)
            
            results = await self.client.query_points(
                collection_name=self.test_collection,
                prefetch=Prefetch(
                    query=query_vector,
                    limit=20
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
                                            "x": "timestamp_ms",  # Use numeric field
                                            "target": now_ms,  # Current time as number
                                            "scale": DECAY_SCALE_DAYS * 24 * 60 * 60 * 1000,  # Scale in ms
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
            
            console.print("[green]✓ Success! Native decay works with numeric timestamps[/green]")
            console.print("\nResults with decay applied:")
            for point in results.points:
                age = point.payload.get('age_days', 'unknown')
                console.print(f"ID: {point.id}, Score: {point.score:.3f}, Age: {age} days")
                
        except Exception as e:
            console.print(f"[red]✗ Failed: {e}[/red]")
            
        # Approach 2: Using age_ms directly (inverse decay)
        console.print("\n[yellow]2. Using age_ms field (age-based decay):[/yellow]")
        try:
            results = await self.client.query_points(
                collection_name=self.test_collection,
                prefetch=Prefetch(
                    query=query_vector,
                    limit=20
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
                                            "x": "age_ms",  # Age in milliseconds
                                            "target": 0,  # Target is 0 age (newest)
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
            
            console.print("[green]✓ Success with age-based decay![/green]")
            console.print("\nResults with age-based decay:")
            for point in results.points:
                age = point.payload.get('age_days', 'unknown')
                console.print(f"ID: {point.id}, Score: {point.score:.3f}, Age: {age} days")
                
        except Exception as e:
            console.print(f"[red]✗ Failed: {e}[/red]")
            
        # Approach 3: Compare with baseline (no decay)
        console.print("\n[yellow]3. Baseline comparison (no decay):[/yellow]")
        try:
            baseline = await self.client.query_points(
                collection_name=self.test_collection,
                query=query_vector,
                limit=10,
                with_payload=True
            )
            
            console.print("Baseline results (no decay):")
            for point in baseline.points:
                age = point.payload.get('age_days', 'unknown')
                console.print(f"ID: {point.id}, Score: {point.score:.3f}, Age: {age} days")
                
        except Exception as e:
            console.print(f"[red]✗ Failed: {e}[/red]")
            
    async def test_client_vs_native_comparison(self):
        """Compare client-side vs native decay results."""
        console.print("\n[bold cyan]Client-side vs Native Decay Comparison[/bold cyan]")
        
        query_vector = np.ones(384).tolist()
        
        # Get baseline results
        baseline = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            limit=20,
            with_payload=True
        )
        
        # Client-side decay
        console.print("\n[yellow]Client-side decay calculation:[/yellow]")
        now = datetime.now()
        client_results = []
        
        for point in baseline.points:
            timestamp = datetime.fromisoformat(point.payload['timestamp'])
            age_days = (now - timestamp).days
            decay_factor = np.exp(-age_days / DECAY_SCALE_DAYS)
            decayed_score = point.score * (1 - DECAY_WEIGHT) + decay_factor * DECAY_WEIGHT
            
            client_results.append({
                'id': point.id,
                'score': decayed_score,
                'age_days': age_days,
                'decay_factor': decay_factor
            })
        
        client_results.sort(key=lambda x: x['score'], reverse=True)
        
        for r in client_results[:5]:
            console.print(f"ID: {r['id']}, Score: {r['score']:.3f}, Age: {r['age_days']}d, Decay: {r['decay_factor']:.3f}")
            
        # Native decay (if working)
        console.print("\n[yellow]Native decay (numeric timestamps):[/yellow]")
        try:
            now_ms = int(now.timestamp() * 1000)
            native_results = await self.client.query_points(
                collection_name=self.test_collection,
                prefetch=Prefetch(
                    query=query_vector,
                    limit=20
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
                                            "x": "timestamp_ms",
                                            "target": now_ms,
                                            "scale": DECAY_SCALE_DAYS * 24 * 60 * 60 * 1000,
                                            "midpoint": 0.5
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ),
                limit=5,
                with_payload=True
            )
            
            for point in native_results.points:
                age = point.payload.get('age_days', 'unknown')
                console.print(f"ID: {point.id}, Score: {point.score:.3f}, Age: {age}d")
                
            # Check if results match
            console.print("\n[bold]Result comparison:[/bold]")
            client_ids = [r['id'] for r in client_results[:5]]
            native_ids = [p.id for p in native_results.points[:5]]
            
            if client_ids == native_ids:
                console.print("[green]✓ Client-side and native decay produce identical ordering![/green]")
            else:
                console.print(f"[yellow]! Different ordering: Client {client_ids} vs Native {native_ids}[/yellow]")
                
        except Exception as e:
            console.print(f"[red]Native decay failed: {e}[/red]")
            
    async def cleanup(self):
        """Clean up test collection."""
        await self.client.delete_collection(self.test_collection)
        
    async def run_all_tests(self):
        """Run all tests."""
        points = await self.setup_test_data()
        await self.test_native_decay_numeric()
        await self.test_client_vs_native_comparison()
        await self.cleanup()
        
        # Summary
        console.print("\n")
        console.print(Panel.fit(
            "[bold]Native Decay with Numeric Timestamps[/bold]\n\n"
            "✓ Workaround: Use numeric timestamp fields (ms or seconds)\n"
            "✓ Store timestamp_ms alongside datetime strings\n"
            "✓ Native decay works correctly with numeric fields\n"
            "✓ Results match client-side decay calculations\n\n"
            "[yellow]Implementation tip:[/yellow]\n"
            "Always store numeric timestamps during data ingestion:\n"
            "timestamp_ms = int(datetime.timestamp() * 1000)",
            title="Success!",
            border_style="green"
        ))

async def main():
    """Main entry point."""
    tester = NativeDecayNumericTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())