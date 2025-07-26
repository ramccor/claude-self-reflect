#!/usr/bin/env python3
"""Test search functionality with Voyage AI embeddings."""

import os
import requests
from qdrant_client import QdrantClient

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")  # Use qdrant hostname in Docker
VOYAGE_API_KEY = os.getenv("VOYAGE_KEY-2") or os.getenv("VOYAGE_KEY")
VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
EMBEDDING_MODEL = "voyage-3.5-lite"

def get_embedding(text):
    """Get embedding for a text using Voyage AI."""
    headers = {
        "Authorization": f"Bearer {VOYAGE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        VOYAGE_API_URL,
        headers=headers,
        json={
            "input": [text],
            "model": EMBEDDING_MODEL,
            "input_type": "query"  # Use query type for search
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Voyage API error: {response.status_code} - {response.text}")
    
    data = response.json()
    return data["data"][0]["embedding"]

def search_collection(query, collection_name, limit=5):
    """Search a specific collection."""
    client = QdrantClient(url=QDRANT_URL)
    
    # Get embedding for query
    print(f"Getting embedding for query: '{query}'")
    query_embedding = get_embedding(query)
    
    # Search
    print(f"Searching in collection: {collection_name}")
    results = client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=limit,
        with_payload=True
    )
    
    return results

def main():
    """Test search functionality."""
    # Test queries
    test_queries = [
        "Voyage AI embeddings",
        "memento stack",
        "Qdrant vector database",
        "Claude conversations"
    ]
    
    # Get a collection to test (memento-stack project)
    collection_name = "conv_ffe14b6c_voyage"  # memento-stack collection
    
    print(f"Testing search on collection: {collection_name}\n")
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: '{query}'")
        print(f"{'='*60}")
        
        try:
            results = search_collection(query, collection_name, limit=3)
            
            if not results:
                print("No results found")
            else:
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. Score: {result.score:.4f}")
                    print(f"   Project: {result.payload.get('project', 'N/A')}")
                    print(f"   File: {result.payload.get('file', 'N/A')}")
                    print(f"   Chunk: {result.payload.get('chunk_index', 'N/A')}")
                    print(f"   Text preview: {result.payload.get('text', '')[:200]}...")
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()