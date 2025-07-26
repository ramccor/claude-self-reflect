#!/usr/bin/env python3
"""
Comprehensive performance comparison of memory decay approaches.
Tests with realistic data volumes and measures latency accurately.
"""

import asyncio
import os
import time
import statistics
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
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))

console = Console()

class PerformanceTestRunner:
    def __init__(self):
        self.client = AsyncQdrantClient(url=QDRANT_URL)
        self.test_collection = "performance_decay_test"
        self.results = {}
        
    async def setup_test_data(self, num_points: int = 1000):
        """Create test collection with realistic data volume."""
        console.print(f"[cyan]Creating test collection with {num_points} points...[/cyan]")
        
        try:
            await self.client.delete_collection(self.test_collection)
        except:
            pass
        
        await self.client.create_collection(
            collection_name=self.test_collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        
        # Create points with varying ages
        now = datetime.now()
        points = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Generating test data...", total=num_points)
            
            for i in range(num_points):
                # Random age between 0 and 365 days
                age_days = np.random.randint(0, 365)
                timestamp = now - timedelta(days=age_days)
                
                # Random vector (simulating embeddings)
                vector = np.random.rand(384).tolist()
                
                points.append(PointStruct(
                    id=i,
                    vector=vector,
                    payload={
                        "text": f"Conversation {i} about topic {i % 10}",
                        "timestamp": timestamp.isoformat(),
                        "age_days": age_days,
                        "project": f"project_{i % 5}"
                    }
                ))
                
                # Batch upload every 100 points
                if len(points) >= 100:
                    await self.client.upsert(
                        collection_name=self.test_collection,
                        points=points
                    )
                    points = []
                    progress.update(task, advance=100)
            
            # Upload remaining points
            if points:
                await self.client.upsert(
                    collection_name=self.test_collection,
                    points=points
                )
                progress.update(task, advance=len(points))
        
        console.print("[green]✓ Test data created successfully[/green]")
    
    async def measure_approach(self, name: str, search_func, iterations: int = 50):
        """Measure performance of an approach."""
        query_vector = np.random.rand(384).tolist()
        latencies = []
        
        # Warm up
        for _ in range(5):
            await search_func(query_vector)
        
        # Actual measurements
        for _ in range(iterations):
            start = time.perf_counter()
            results = await search_func(query_vector)
            latency = (time.perf_counter() - start) * 1000  # Convert to ms
            latencies.append(latency)
        
        return {
            'mean': statistics.mean(latencies),
            'median': statistics.median(latencies),
            'stdev': statistics.stdev(latencies) if len(latencies) > 1 else 0,
            'min': min(latencies),
            'max': max(latencies),
            'p95': statistics.quantiles(latencies, n=20)[18] if len(latencies) > 1 else latencies[0],
            'p99': statistics.quantiles(latencies, n=100)[98] if len(latencies) > 1 else latencies[0],
            'result_count': len(results) if results else 0
        }
    
    async def baseline_search(self, query_vector):
        """Standard search without decay."""
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            limit=10
        )
        return response.points
    
    async def client_side_decay(self, query_vector):
        """Client-side decay calculation."""
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            limit=30,  # Get extra for reranking
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
            results.append((decayed_score, point))
        
        # Sort and return top 10
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:10]]
    
    async def payload_filtering(self, query_vector):
        """Payload-based time window filtering."""
        response = await self.client.query_points(
            collection_name=self.test_collection,
            query=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="age_days",
                        range=Range(lte=90)  # Last 90 days
                    )
                ]
            ),
            limit=10
        )
        return response.points
    
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
                # Older but relevant
                Prefetch(
                    query=query_vector,
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="age_days",
                                range=Range(gte=31, lte=90)
                            )
                        ]
                    ),
                    limit=10
                )
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=10
        )
        return response.points
    
    async def run_performance_tests(self, num_points: int = 1000):
        """Run all performance tests."""
        await self.setup_test_data(num_points)
        
        console.print("\n[bold cyan]Running Performance Tests...[/bold cyan]")
        
        approaches = [
            ("Baseline (No Decay)", self.baseline_search),
            ("Client-Side Decay", self.client_side_decay),
            ("Payload Filtering", self.payload_filtering),
            ("Hybrid Fusion", self.hybrid_fusion),
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            for name, func in approaches:
                task = progress.add_task(f"Testing {name}...", total=1)
                self.results[name] = await self.measure_approach(name, func)
                progress.update(task, advance=1)
        
        # Display results
        self.display_results()
        
        # Cleanup
        await self.client.delete_collection(self.test_collection)
    
    def display_results(self):
        """Display performance comparison results."""
        console.print("\n[bold green]Performance Comparison Results[/bold green]")
        
        # Create comparison table
        table = Table(title="Latency Comparison (milliseconds)")
        table.add_column("Approach", style="cyan", no_wrap=True)
        table.add_column("Mean", style="yellow")
        table.add_column("Median", style="yellow")
        table.add_column("StdDev", style="dim")
        table.add_column("P95", style="magenta")
        table.add_column("P99", style="red")
        table.add_column("Min-Max", style="dim")
        
        baseline_mean = None
        for name, stats in self.results.items():
            if baseline_mean is None:
                baseline_mean = stats['mean']
            
            overhead = f" (+{stats['mean'] - baseline_mean:.1f}ms)" if baseline_mean and name != "Baseline (No Decay)" else ""
            
            table.add_row(
                name,
                f"{stats['mean']:.2f}{overhead}",
                f"{stats['median']:.2f}",
                f"{stats['stdev']:.2f}",
                f"{stats['p95']:.2f}",
                f"{stats['p99']:.2f}",
                f"{stats['min']:.1f}-{stats['max']:.1f}"
            )
        
        console.print(table)
        
        # Ranking
        console.print("\n[bold]Performance Ranking (by median latency):[/bold]")
        ranked = sorted(self.results.items(), key=lambda x: x[1]['median'])
        for i, (name, stats) in enumerate(ranked, 1):
            console.print(f"{i}. [green]{name}[/green]: {stats['median']:.2f}ms median")
        
        # Recommendations
        console.print("\n[bold yellow]Recommendations:[/bold yellow]")
        fastest = ranked[0][0]
        console.print(f"• [green]Fastest approach:[/green] {fastest}")
        
        if fastest == "Baseline (No Decay)":
            console.print("• Consider if decay is necessary for your use case")
        elif fastest == "Payload Filtering":
            console.print("• Good for hard time cutoffs, but no gradual decay")
        elif fastest == "Client-Side Decay":
            console.print("• Most flexible with minimal overhead")
        elif fastest == "Hybrid Fusion":
            console.print("• Good balance of performance and time-based relevance")

async def main():
    """Main entry point."""
    runner = PerformanceTestRunner()
    
    # Test with different data sizes
    for size in [1000, 5000]:
        console.print(f"\n[bold blue]Testing with {size} points[/bold blue]")
        await runner.run_performance_tests(size)
        console.print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())