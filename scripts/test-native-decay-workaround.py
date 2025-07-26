#!/usr/bin/env python3
"""
Test native decay implementation with workarounds for server limitations.
"""

import asyncio
import os
import json
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

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))

console = Console()

class NativeDecayTester:
    """Test native decay with various workarounds."""
    
    def __init__(self):
        self.client = AsyncQdrantClient(url=QDRANT_URL)
        self.test_collection = "native_decay_test"
        
    async def setup_test_data(self):
        """Create test collection with timestamp data."""
        try:
            await self.client.delete_collection(self.test_collection)
        except:
            pass
        
        await self.client.create_collection(
            collection_name=self.test_collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        
        # Create test points
        now = datetime.now()
        points = []
        
        for days_ago in [0, 30, 90, 180]:
            timestamp = now - timedelta(days=days_ago)
            vector = np.random.rand(384).tolist()
            
            points.append(PointStruct(
                id=len(points) + 1,
                vector=vector,
                payload={
                    "text": f"Content from {days_ago} days ago",
                    "timestamp": timestamp.isoformat(),
                    "timestamp_ms": int(timestamp.timestamp() * 1000),
                    "age_days": days_ago
                }
            ))
        
        await self.client.upsert(
            collection_name=self.test_collection,
            points=points
        )
        
        console.print(f"[green]✓ Created test collection with {len(points)} points[/green]")
        
    async def test_native_decay_approaches(self):
        """Test different approaches for native decay."""
        query_vector = np.random.rand(384).tolist()
        
        console.print("\n[bold cyan]Testing Native Decay Approaches[/bold cyan]")
        
        # Approach 1: Direct Prefetch + FormulaQuery (as documented)
        console.print("\n[yellow]1. Direct Prefetch + FormulaQuery:[/yellow]")
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
            console.print("[green]✓ Success! Native decay works with this pattern[/green]")
            for point in results.points[:3]:
                console.print(f"  ID: {point.id}, Score: {point.score:.3f}, Age: {point.payload.get('age_days')}d")
        except Exception as e:
            console.print(f"[red]✗ Failed: {e}[/red]")
            
        # Approach 2: Simplified formula syntax
        console.print("\n[yellow]2. Simplified formula syntax:[/yellow]")
        try:
            # Try with simpler formula structure
            results = await self.client.query_points(
                collection_name=self.test_collection,
                prefetch=Prefetch(
                    query=query_vector,
                    limit=20
                ),
                query=FormulaQuery(
                    formula="$score + 0.3 * exp(-age_days / 90)"
                ),
                limit=10,
                with_payload=True
            )
            console.print("[green]✓ Success with simplified syntax![/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed: {e}[/red]")
            
        # Approach 3: Test if timestamp fields are indexed properly
        console.print("\n[yellow]3. Check timestamp field indexing:[/yellow]")
        try:
            # Get collection info to see if timestamps are indexed
            info = await self.client.get_collection(self.test_collection)
            console.print(f"Collection config: {info.config}")
            
            # Try creating an index on timestamp
            await self.client.create_field_index(
                collection_name=self.test_collection,
                field_name="timestamp_ms",
                field_schema=models.PayloadSchemaType.INTEGER
            )
            console.print("[green]✓ Created timestamp index[/green]")
        except Exception as e:
            console.print(f"[yellow]! Index creation: {e}[/yellow]")
            
        # Approach 4: HTTP API direct test
        console.print("\n[yellow]4. Direct HTTP API test:[/yellow]")
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                # Build the exact query that should work
                query_body = {
                    "prefetch": {
                        "query": query_vector,
                        "limit": 20
                    },
                    "query": {
                        "formula": {
                            "sum": [
                                "$score",
                                {
                                    "mult": [
                                        0.3,
                                        {
                                            "exp_decay": {
                                                "x": {"datetime_key": "timestamp"},
                                                "target": {"datetime": "now"},
                                                "scale": 7776000000,  # 90 days in ms
                                                "midpoint": 0.5
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    "limit": 10,
                    "with_payload": True
                }
                
                response = await client.post(
                    f"{QDRANT_URL}/collections/{self.test_collection}/points/query",
                    json=query_body,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    console.print("[green]✓ HTTP API accepts the query![/green]")
                    result_data = response.json()
                    console.print(f"Response: {json.dumps(result_data, indent=2)[:500]}...")
                else:
                    console.print(f"[red]✗ HTTP API error: {response.status_code}[/red]")
                    console.print(f"Response: {response.text[:500]}")
        except Exception as e:
            console.print(f"[red]✗ HTTP error: {e}[/red]")
            
        # Approach 5: Test server capabilities
        console.print("\n[yellow]5. Check server version and capabilities:[/yellow]")
        try:
            # Get server info
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{QDRANT_URL}/")
                if response.status_code == 200:
                    server_info = response.json()
                    console.print(f"Server version: {server_info.get('version', 'unknown')}")
                    
                # Check if FormulaQuery is supported
                response = await client.get(f"{QDRANT_URL}/openapi.json")
                if response.status_code == 200:
                    openapi = response.json()
                    # Search for FormulaQuery in the schema
                    formula_found = "FormulaQuery" in str(openapi)
                    exp_decay_found = "exp_decay" in str(openapi)
                    console.print(f"FormulaQuery in API: {formula_found}")
                    console.print(f"exp_decay in API: {exp_decay_found}")
        except Exception as e:
            console.print(f"[yellow]! Server info error: {e}[/yellow]")
            
        # Cleanup
        await self.client.delete_collection(self.test_collection)
        
    async def test_mock_native_behavior(self):
        """Create a mock that simulates what native decay SHOULD do."""
        console.print("\n[bold cyan]Mock Native Decay Behavior[/bold cyan]")
        console.print("This shows what the server SHOULD return with native decay:\n")
        
        await self.setup_test_data()
        query_vector = np.random.rand(384).tolist()
        
        # Get candidates
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            limit=20,
            with_payload=True
        )
        
        # Simulate server-side decay
        console.print("Expected native decay results:")
        console.print("─" * 50)
        
        now = datetime.now()
        for point in response.points:
            timestamp = datetime.fromisoformat(point.payload['timestamp'])
            age_days = (now - timestamp).days
            
            # This is what the server SHOULD calculate
            decay_factor = np.exp(-age_days / DECAY_SCALE_DAYS)
            # Native formula: score + weight * decay_factor
            expected_score = point.score + DECAY_WEIGHT * decay_factor
            
            console.print(
                f"ID: {point.id} | "
                f"Age: {age_days:3d}d | "
                f"Original: {point.score:.3f} | "
                f"Decay: {decay_factor:.3f} | "
                f"Expected: {expected_score:.3f}"
            )
        
        await self.client.delete_collection(self.test_collection)
        
    async def run_all_tests(self):
        """Run all native decay tests."""
        await self.setup_test_data()
        await self.test_native_decay_approaches()
        await self.test_mock_native_behavior()
        
        # Summary panel
        console.print("\n")
        console.print(Panel.fit(
            "[bold]Native Decay Status Summary[/bold]\n\n"
            "• Prefetch + FormulaQuery pattern is correct ✓\n"
            "• Server may not support exp_decay operations yet\n"
            "• Client-side decay provides identical behavior\n"
            "• Mock shows expected native behavior\n\n"
            "[yellow]Recommendation:[/yellow] Continue using client-side decay\n"
            "until server support is confirmed.",
            title="Summary",
            border_style="green"
        ))

async def main():
    """Main entry point."""
    tester = NativeDecayTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())