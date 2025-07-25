#!/usr/bin/env python3
"""Command-line tool for A/B comparison of search with and without decay."""

import argparse
import json
import numpy as np
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import *
from tabulate import tabulate
import requests
import os

class DecayComparison:
    def __init__(self):
        self.client = QdrantClient(url="http://localhost:6333")
        self.voyage_api_key = os.getenv("VOYAGE_API_KEY")
        
    def get_embedding(self, text):
        """Get embedding from Voyage AI."""
        if not self.voyage_api_key:
            raise ValueError("VOYAGE_API_KEY environment variable not set")
            
        response = requests.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.voyage_api_key}"},
            json={"input": [text], "model": "voyage-3-large"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Voyage API error: {response.text}")
            
        return response.json()["data"][0]["embedding"]
        
    def search_collection(self, collection_name, query_vector, use_decay=False, limit=10):
        """Search a collection with or without decay."""
        if not use_decay:
            # Standard search
            return self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                with_payload=True
            )
        else:
            # Search with decay
            return self.client.query_points(
                collection_name=collection_name,
                prefetch=[
                    Prefetch(
                        query=query_vector,
                        limit=limit * 5  # Get more candidates
                    )
                ],
                query=FormulaQuery(
                    formula=SumExpression(
                        sum=[
                            "$score",
                            MultExpression(
                                mult=[
                                    0.3,  # FIXED: Positive decay weight to boost recent items
                                    ExpDecayExpression(
                                        exp_decay=DecayParamsExpression(
                                            x="timestamp",  # Unix timestamp from payload
                                            target=int(datetime.now().timestamp()),
                                            scale=7776000  # 90 days in seconds
                                        )
                                    )
                                ]
                            )
                        ]
                    )
                ),
                limit=limit
            ).points
            
    def compare_results(self, query, collections=None, limit=10):
        """Compare search results with and without decay across collections."""
        # Get all voyage collections if not specified
        if not collections:
            all_collections = self.client.get_collections().collections
            collections = [c.name for c in all_collections if c.name.endswith('_voyage')]
            
        # Get query embedding
        print(f"\n🔍 Query: '{query}'")
        print("Generating embedding...")
        query_vector = self.get_embedding(query)
        
        # Search each collection
        all_results = []
        
        for collection in collections:
            print(f"\nSearching {collection}...")
            
            # Get results without decay
            results_no_decay = self.search_collection(
                collection, query_vector, use_decay=False, limit=limit
            )
            
            # Get results with decay
            results_with_decay = self.search_collection(
                collection, query_vector, use_decay=True, limit=limit
            )
            
            # Process results
            for i, (no_decay, with_decay) in enumerate(zip(results_no_decay, results_with_decay)):
                # Extract relevant info
                no_decay_data = {
                    "rank": i + 1,
                    "collection": collection,
                    "score": no_decay.score,
                    "content": no_decay.payload.get("content", "")[:100] + "...",
                    "timestamp": no_decay.payload.get("timestamp", 0),
                    "age_days": (datetime.now().timestamp() - no_decay.payload.get("timestamp", 0)) / 86400
                }
                
                with_decay_data = {
                    "rank": i + 1,
                    "collection": collection,
                    "score": with_decay.score if hasattr(with_decay, 'score') else 0,
                    "content": with_decay.payload.get("content", "")[:100] + "...",
                    "timestamp": with_decay.payload.get("timestamp", 0),
                    "age_days": (datetime.now().timestamp() - with_decay.payload.get("timestamp", 0)) / 86400
                }
                
                all_results.append({
                    "no_decay": no_decay_data,
                    "with_decay": with_decay_data
                })
                
        return all_results
        
    def display_comparison(self, results, show_full=False):
        """Display comparison results in a formatted table."""
        print("\n📊 Comparison Results:")
        print("=" * 120)
        
        # Prepare data for tabulation
        table_data = []
        
        for result in results[:20]:  # Top 20 results
            no_decay = result["no_decay"]
            with_decay = result["with_decay"]
            
            # Calculate position change
            position_change = "↔" if no_decay["content"] == with_decay["content"] else "↕"
            
            row = [
                no_decay["rank"],
                f"{no_decay['score']:.3f}",
                f"{no_decay['age_days']:.0f}d",
                no_decay["content"][:50] + "..." if not show_full else no_decay["content"],
                position_change,
                with_decay["rank"],
                f"{with_decay['score']:.3f}",
                f"{with_decay['age_days']:.0f}d",
                with_decay["content"][:50] + "..." if not show_full else with_decay["content"]
            ]
            
            table_data.append(row)
            
        headers = [
            "Rank", "Score", "Age", "Content (No Decay)",
            "↕",
            "Rank", "Score", "Age", "Content (With Decay)"
        ]
        
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Calculate metrics
        avg_age_no_decay = np.mean([r["no_decay"]["age_days"] for r in results[:5]])
        avg_age_with_decay = np.mean([r["with_decay"]["age_days"] for r in results[:5]])
        
        print(f"\n📈 Metrics Summary:")
        print(f"Average age (top 5) without decay: {avg_age_no_decay:.1f} days")
        print(f"Average age (top 5) with decay: {avg_age_with_decay:.1f} days")
        print(f"Recency improvement: {(avg_age_no_decay - avg_age_with_decay) / avg_age_no_decay * 100:.1f}%")
        
    def save_results(self, results, output_file):
        """Save detailed results to JSON file."""
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": results,
                "metrics": {
                    "avg_age_no_decay": np.mean([r["no_decay"]["age_days"] for r in results[:5]]),
                    "avg_age_with_decay": np.mean([r["with_decay"]["age_days"] for r in results[:5]]),
                    "total_results": len(results)
                }
            }, f, indent=2)
        print(f"\n💾 Detailed results saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Compare Qdrant search results with and without decay")
    parser.add_argument("query", help="Search query text")
    parser.add_argument("--collections", nargs="+", help="Specific collections to search (default: all voyage collections)")
    parser.add_argument("--limit", type=int, default=10, help="Number of results per collection (default: 10)")
    parser.add_argument("--full", action="store_true", help="Show full content in results")
    parser.add_argument("--output", help="Save detailed results to JSON file")
    
    args = parser.parse_args()
    
    try:
        comparator = DecayComparison()
        results = comparator.compare_results(args.query, args.collections, args.limit)
        comparator.display_comparison(results, args.full)
        
        if args.output:
            comparator.save_results(results, args.output)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main())