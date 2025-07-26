#!/usr/bin/env python3
"""
Demonstration of memory decay approaches for Qdrant.
This script shows the practical implementation of different decay methods.
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import PointStruct, VectorParams, Distance
import numpy as np
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Load environment
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

QDRANT_URL = os.getenv('QDRANT_URL', 'http://localhost:6333')
DECAY_WEIGHT = float(os.getenv('DECAY_WEIGHT', '0.3'))
DECAY_SCALE_DAYS = float(os.getenv('DECAY_SCALE_DAYS', '90'))

console = Console()

async def main():
    """Demonstrate memory decay approaches."""
    client = AsyncQdrantClient(url=QDRANT_URL)
    
    # Create demo collection
    collection = "decay_demo"
    try:
        await client.delete_collection(collection)
    except:
        pass
    
    await client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=4, distance=Distance.COSINE)
    )
    
    # Insert test data
    now = datetime.now()
    points = [
        PointStruct(
            id=1,
            vector=[1.0, 0.0, 0.0, 0.0],
            payload={
                "text": "Today: Latest React 19 features announced",
                "timestamp": now.isoformat(),
                "age_days": 0
            }
        ),
        PointStruct(
            id=2,
            vector=[0.9, 0.1, 0.0, 0.0],
            payload={
                "text": "1 week ago: React Server Components guide",
                "timestamp": (now - timedelta(days=7)).isoformat(),
                "age_days": 7
            }
        ),
        PointStruct(
            id=3,
            vector=[0.8, 0.2, 0.0, 0.0],
            payload={
                "text": "1 month ago: React hooks best practices",
                "timestamp": (now - timedelta(days=30)).isoformat(),
                "age_days": 30
            }
        ),
        PointStruct(
            id=4,
            vector=[0.7, 0.3, 0.0, 0.0],
            payload={
                "text": "3 months ago: React performance tips",
                "timestamp": (now - timedelta(days=90)).isoformat(),
                "age_days": 90
            }
        ),
    ]
    
    await client.upsert(collection_name=collection, points=points)
    
    query_vector = [0.95, 0.05, 0.0, 0.0]  # Similar to recent React content
    
    console.print(Panel.fit("🧠 Memory Decay Demonstration", style="bold blue"))
    
    # 1. Standard Search (No Decay)
    console.print("\n[bold green]1. Standard Search (No Decay)[/bold green]")
    results = await client.search(
        collection_name=collection,
        query_vector=query_vector,
        limit=4,
        with_payload=True
    )
    
    table = Table(title="Standard Results")
    table.add_column("Score", style="cyan")
    table.add_column("Age", style="yellow")
    table.add_column("Content", style="white")
    
    for r in results:
        table.add_row(
            f"{r.score:.3f}",
            f"{r.payload['age_days']} days",
            r.payload['text']
        )
    console.print(table)
    
    # 2. Client-Side Decay (Current Implementation)
    console.print("\n[bold green]2. Client-Side Decay (Current Implementation)[/bold green]")
    
    # Get more results for reranking
    results = await client.search(
        collection_name=collection,
        query_vector=query_vector,
        limit=10,
        with_payload=True
    )
    
    # Apply decay
    decayed_results = []
    for r in results:
        age_days = r.payload['age_days']
        decay_factor = np.exp(-age_days / DECAY_SCALE_DAYS)
        decayed_score = r.score * (1 - DECAY_WEIGHT) + decay_factor * DECAY_WEIGHT
        decayed_results.append({
            'original': r,
            'decay_factor': decay_factor,
            'decayed_score': decayed_score
        })
    
    # Sort by decayed score
    decayed_results.sort(key=lambda x: x['decayed_score'], reverse=True)
    
    table = Table(title="Client-Side Decay Results")
    table.add_column("Original", style="dim")
    table.add_column("Decay", style="magenta")
    table.add_column("Final", style="cyan")
    table.add_column("Age", style="yellow")
    table.add_column("Content", style="white")
    
    for dr in decayed_results[:4]:
        r = dr['original']
        table.add_row(
            f"{r.score:.3f}",
            f"{dr['decay_factor']:.3f}",
            f"{dr['decayed_score']:.3f}",
            f"{r.payload['age_days']} days",
            r.payload['text']
        )
    console.print(table)
    
    # 3. Native Decay (Correct Implementation)
    console.print("\n[bold green]3. Native Decay (Prefetch + FormulaQuery)[/bold green]")
    
    try:
        results = await client.query_points(
            collection_name=collection,
            prefetch=models.Prefetch(
                query=query_vector,
                limit=20
            ),
            query=models.FormulaQuery(
                formula={
                    "sum": [
                        "$score",  # Reference to prefetch score
                        {
                            "mult": [
                                DECAY_WEIGHT,  # Decay weight constant
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
            limit=4,
            with_payload=True
        )
        
        table = Table(title="Native Decay Results (Server-Side)")
        table.add_column("Score", style="cyan")
        table.add_column("Age", style="yellow") 
        table.add_column("Content", style="white")
        
        for r in results.points:
            table.add_row(
                f"{r.score:.3f}",
                f"{r.payload['age_days']} days",
                r.payload['text']
            )
        console.print(table)
        console.print("[green]✅ Native decay works correctly![/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Native decay error: {e}[/red]")
        console.print("[yellow]This may require Qdrant server update[/yellow]")
    
    # Summary
    console.print(Panel(
        "[bold]Key Findings:[/bold]\n\n"
        "1. [cyan]Standard search[/cyan]: Orders by vector similarity only\n"
        "2. [magenta]Client-side decay[/magenta]: Adds time-based boost after retrieval\n"
        "3. [green]Native decay[/green]: Server-side calculation, most efficient\n\n"
        "[yellow]Recommendation:[/yellow] Use client-side decay until native support is verified",
        title="Summary",
        style="bold"
    ))
    
    # Cleanup
    await client.delete_collection(collection)

if __name__ == "__main__":
    asyncio.run(main())