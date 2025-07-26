#!/usr/bin/env python3
"""
Test decay result quality across different approaches.
Focuses on how different decay methods affect result ordering and scores,
not just performance speed.
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import (
    PointStruct, VectorParams, Distance, Filter, FieldCondition, Range,
    Prefetch, FormulaQuery, FusionQuery, Fusion
)
import numpy as np
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
import json

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))

console = Console()

class DecayQualityTester:
    """Test the quality of search results with different decay approaches."""
    
    def __init__(self):
        self.client = AsyncQdrantClient(url=QDRANT_URL)
        self.test_collection = "decay_quality_test"
        self.results = {}
        
    async def setup_test_data(self):
        """Create test data with clear temporal patterns."""
        console.print("[cyan]Setting up test data with temporal patterns...[/cyan]")
        
        # Delete if exists
        try:
            await self.client.delete_collection(self.test_collection)
        except:
            pass
        
        # Create collection
        await self.client.create_collection(
            collection_name=self.test_collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        
        # Create test points with specific patterns
        now = datetime.now()
        points = []
        
        # Pattern 1: Same content at different times
        base_vector = np.random.rand(384).tolist()
        for days_ago in [0, 30, 90, 180, 365]:
            timestamp = now - timedelta(days=days_ago)
            points.append(PointStruct(
                id=len(points) + 1,
                vector=base_vector,  # Same vector!
                payload={
                    "text": "React hooks useEffect cleanup pattern",
                    "timestamp": timestamp.isoformat(),
                    "age_days": days_ago,
                    "content_id": "identical_content",
                    "freshness": "fresh" if days_ago < 30 else "old"
                }
            ))
        
        # Pattern 2: Similar content with slight variations
        for i, (days_ago, similarity) in enumerate([(0, 0.95), (30, 0.90), (90, 0.85), (180, 0.80)]):
            timestamp = now - timedelta(days=days_ago)
            # Create slightly different vectors
            vector = base_vector.copy()
            noise = np.random.normal(0, 0.1 * (1 - similarity), 384)
            vector = (np.array(vector) + noise).tolist()
            
            points.append(PointStruct(
                id=len(points) + 1,
                vector=vector,
                payload={
                    "text": f"React hooks useEffect pattern variation {i}",
                    "timestamp": timestamp.isoformat(),
                    "age_days": days_ago,
                    "content_id": f"similar_content_{i}",
                    "similarity_to_query": similarity,
                    "freshness": "fresh" if days_ago < 30 else "old"
                }
            ))
        
        # Pattern 3: Different topics at different times
        topics = [
            ("React hooks", 10),
            ("Vue composition API", 60),
            ("Angular signals", 120),
            ("Svelte stores", 240)
        ]
        
        for topic, days_ago in topics:
            timestamp = now - timedelta(days=days_ago)
            # Random vectors for different topics
            vector = np.random.rand(384).tolist()
            
            points.append(PointStruct(
                id=len(points) + 1,
                vector=vector,
                payload={
                    "text": f"Tutorial about {topic}",
                    "timestamp": timestamp.isoformat(),
                    "age_days": days_ago,
                    "content_id": f"topic_{topic.replace(' ', '_')}",
                    "topic": topic,
                    "freshness": "fresh" if days_ago < 30 else "old"
                }
            ))
        
        # Insert all points
        await self.client.upsert(
            collection_name=self.test_collection,
            points=points
        )
        
        console.print(f"[green]✓ Created {len(points)} test points with temporal patterns[/green]")
        return points
    
    async def baseline_search(self, query_vector):
        """Standard search without decay."""
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            limit=10,
            with_payload=True
        )
        return response.points
    
    async def client_side_decay(self, query_vector):
        """Client-side decay calculation."""
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            limit=20,  # Get extra for reranking
            with_payload=True
        )
        
        # Apply decay
        now = datetime.now()
        results = []
        for point in response.points:
            timestamp = datetime.fromisoformat(point.payload['timestamp'])
            age_days = (now - timestamp).days
            decay_factor = np.exp(-age_days / DECAY_SCALE_DAYS)
            decayed_score = point.score * (1 - DECAY_WEIGHT) + decay_factor * DECAY_WEIGHT
            
            # Store both scores for analysis
            point.payload['original_score'] = point.score
            point.payload['decay_factor'] = decay_factor
            point.payload['decayed_score'] = decayed_score
            point.score = decayed_score
            results.append(point)
        
        # Sort and return top 10
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:10]
    
    async def payload_filtering(self, query_vector):
        """Payload-based time window filtering."""
        # Search only recent items
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="age_days",
                        range=Range(lte=60)  # Last 60 days only
                    )
                ]
            ),
            limit=10,
            with_payload=True
        )
        return response.points
    
    async def native_decay_mock(self, query_vector):
        """Mock native decay to show expected behavior."""
        # Since native decay fails, we'll simulate what it SHOULD do
        # This helps us understand if the similar results are expected
        
        # Get candidates
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            limit=20,
            with_payload=True
        )
        
        # Simulate server-side decay calculation
        now = datetime.now()
        results = []
        for point in response.points:
            timestamp = datetime.fromisoformat(point.payload['timestamp'])
            age_days = (now - timestamp).days
            
            # This simulates what the server SHOULD do with FormulaQuery
            decay_factor = np.exp(-age_days / DECAY_SCALE_DAYS)
            # Server would use: score + DECAY_WEIGHT * decay_factor
            # But we'll use the same formula as client-side for comparison
            decayed_score = point.score * (1 - DECAY_WEIGHT) + decay_factor * DECAY_WEIGHT
            
            point.payload['original_score'] = point.score
            point.payload['decay_factor'] = decay_factor
            point.payload['decayed_score'] = decayed_score
            point.payload['decay_method'] = 'native_mock'
            point.score = decayed_score
            results.append(point)
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:10]
    
    async def hybrid_fusion(self, query_vector):
        """Hybrid search with fusion."""
        response = await self.client.query_points(
            collection_name=self.test_collection,
            prefetch=[
                # Recent content
                Prefetch(
                    query=query_vector,
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="age_days",
                                range=Range(lte=30)
                            )
                        ]
                    ),
                    limit=10
                ),
                # Older content
                Prefetch(
                    query=query_vector,
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="age_days",
                                range=Range(gte=31)
                            )
                        ]
                    ),
                    limit=10
                )
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=10,
            with_payload=True
        )
        return response.points
    
    def analyze_result_differences(self, results_dict):
        """Analyze how different approaches affect result ordering."""
        console.print("\n[bold cyan]Result Quality Analysis[/bold cyan]")
        
        # Compare top results across approaches
        table = Table(title="Top 5 Results Comparison")
        table.add_column("Rank", style="cyan", no_wrap=True)
        
        for approach in results_dict:
            table.add_column(approach, style="yellow")
        
        # Show top 5 for each approach
        for rank in range(5):
            row = [str(rank + 1)]
            for approach, results in results_dict.items():
                if rank < len(results):
                    point = results[rank]
                    age = point.payload.get('age_days', 'N/A')
                    score = point.score
                    content_id = point.payload.get('content_id', 'unknown')
                    row.append(f"ID:{point.id}\nAge:{age}d\nScore:{score:.3f}\n{content_id[:20]}")
                else:
                    row.append("—")
            table.add_row(*row)
        
        console.print(table)
        
        # Analyze ranking differences
        console.print("\n[bold]Ranking Differences:[/bold]")
        
        # Get ID order for each approach
        id_orders = {}
        for approach, results in results_dict.items():
            id_orders[approach] = [p.id for p in results[:10]]
        
        # Compare to baseline
        baseline_order = id_orders.get("Baseline", [])
        for approach, order in id_orders.items():
            if approach == "Baseline":
                continue
            
            # Calculate ranking correlation
            common_ids = set(baseline_order) & set(order)
            if common_ids:
                # Simple position difference metric
                position_diffs = []
                for id in common_ids:
                    if id in baseline_order and id in order:
                        baseline_pos = baseline_order.index(id)
                        approach_pos = order.index(id)
                        position_diffs.append(abs(baseline_pos - approach_pos))
                
                avg_position_change = sum(position_diffs) / len(position_diffs) if position_diffs else 0
                console.print(f"{approach}: Avg position change from baseline: {avg_position_change:.1f}")
            
        # Score distribution analysis
        console.print("\n[bold]Score Distribution:[/bold]")
        for approach, results in results_dict.items():
            if results:
                scores = [p.score for p in results[:10]]
                console.print(f"{approach}:")
                console.print(f"  Range: {min(scores):.3f} - {max(scores):.3f}")
                console.print(f"  Spread: {max(scores) - min(scores):.3f}")
                
                # Check if decay is actually applied
                if approach in ["Client-side Decay", "Native Mock"]:
                    # Look for decay evidence
                    has_decay_info = any('decayed_score' in p.payload for p in results)
                    if has_decay_info:
                        decay_factors = [p.payload.get('decay_factor', 0) for p in results if 'decay_factor' in p.payload]
                        if decay_factors:
                            console.print(f"  Decay factors: {min(decay_factors):.3f} - {max(decay_factors):.3f}")
    
    def create_visual_comparison(self, results_dict):
        """Create visual comparison of how decay affects identical content."""
        console.print("\n[bold cyan]Identical Content at Different Ages:[/bold cyan]")
        
        # Find identical content across time
        for approach, results in results_dict.items():
            identical_points = [p for p in results if p.payload.get('content_id') == 'identical_content']
            
            if identical_points:
                console.print(f"\n[yellow]{approach}:[/yellow]")
                for point in identical_points[:5]:  # Show up to 5
                    age = point.payload.get('age_days', 'N/A')
                    score = point.score
                    original = point.payload.get('original_score', score)
                    decay_factor = point.payload.get('decay_factor', 'N/A')
                    
                    # Visual score bar
                    bar_length = int(score * 20)
                    score_bar = "█" * bar_length + "░" * (20 - bar_length)
                    
                    console.print(f"  Age {age:3d}d: [{score_bar}] {score:.3f}", end="")
                    if isinstance(decay_factor, float):
                        console.print(f" (original: {original:.3f}, decay: {decay_factor:.3f})")
                    else:
                        console.print()
    
    async def run_quality_tests(self):
        """Run comprehensive quality tests."""
        # Setup test data
        test_points = await self.setup_test_data()
        
        # Use the first identical content point as query
        query_vector = test_points[0].vector
        
        console.print("\n[cyan]Running quality tests on all approaches...[/cyan]")
        
        # Test all approaches
        approaches = [
            ("Baseline", self.baseline_search),
            ("Client-side Decay", self.client_side_decay),
            ("Payload Filter", self.payload_filtering),
            ("Native Mock", self.native_decay_mock),
            ("Hybrid Fusion", self.hybrid_fusion),
        ]
        
        results_dict = {}
        for name, func in approaches:
            try:
                console.print(f"Testing {name}...")
                results = await func(query_vector)
                results_dict[name] = results
            except Exception as e:
                console.print(f"[red]Error in {name}: {e}[/red]")
                results_dict[name] = []
        
        # Analyze differences
        self.analyze_result_differences(results_dict)
        self.create_visual_comparison(results_dict)
        
        # Test with temporal-sensitive query
        console.print("\n[bold cyan]Testing with Temporal-Sensitive Query[/bold cyan]")
        console.print("Query: 'Recent React patterns' (should prefer fresh content)")
        
        # Create a query vector that's similar to React content
        react_points = [p for p in test_points if 'React' in p.payload.get('text', '')]
        if react_points:
            query_vector = react_points[0].vector
            
            temporal_results = {}
            for name, func in approaches:
                try:
                    results = await func(query_vector)
                    temporal_results[name] = results
                except:
                    temporal_results[name] = []
            
            # Show age distribution in results
            console.print("\n[bold]Age Distribution in Top 5 Results:[/bold]")
            for approach, results in temporal_results.items():
                ages = [p.payload.get('age_days', -1) for p in results[:5]]
                if ages:
                    console.print(f"{approach}: {ages} (avg: {sum(ages)/len(ages):.0f} days)")
        
        # Save detailed results
        self.save_detailed_results(results_dict)
        
        # Cleanup
        await self.client.delete_collection(self.test_collection)
        
        return results_dict
    
    def save_detailed_results(self, results_dict):
        """Save detailed results for analysis."""
        output = {
            "test_timestamp": datetime.now().isoformat(),
            "decay_config": {
                "weight": DECAY_WEIGHT,
                "scale_days": DECAY_SCALE_DAYS
            },
            "approaches": {}
        }
        
        for approach, results in results_dict.items():
            output["approaches"][approach] = {
                "results": [
                    {
                        "id": p.id,
                        "score": p.score,
                        "age_days": p.payload.get('age_days'),
                        "content_id": p.payload.get('content_id'),
                        "original_score": p.payload.get('original_score'),
                        "decay_factor": p.payload.get('decay_factor'),
                        "text": p.payload.get('text')
                    }
                    for p in results[:10]
                ]
            }
        
        output_file = Path(__file__).parent / "decay_quality_results.json"
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        console.print(f"\n[green]Detailed results saved to: {output_file}[/green]")

async def main():
    """Main entry point."""
    tester = DecayQualityTester()
    results = await tester.run_quality_tests()
    
    # Final verdict
    console.print("\n[bold red]FINDINGS:[/bold red]")
    console.print("1. Are all approaches returning similar results? Check the ranking differences above.")
    console.print("2. Is decay actually working? Check the score distributions and decay factors.")
    console.print("3. Which approach provides the best temporal relevance? Check age distributions.")

if __name__ == "__main__":
    asyncio.run(main())