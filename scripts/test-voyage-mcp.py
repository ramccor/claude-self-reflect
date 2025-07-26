#!/usr/bin/env python3
"""Test if Voyage collections have the correct data structure."""

import os
from qdrant_client import QdrantClient

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

def main():
    """Check a sample point from a Voyage collection."""
    client = QdrantClient(url=QDRANT_URL)
    
    # Get a sample collection
    collection_name = "conv_ffe14b6c_voyage"  # memento-stack collection
    
    print(f"Checking collection: {collection_name}")
    
    # Get collection info
    info = client.get_collection(collection_name)
    print(f"Vectors config: {info.config.params.vectors}")
    print(f"Points count: {info.points_count}")
    
    # Get a sample point
    points = client.scroll(
        collection_name=collection_name,
        limit=1,
        with_payload=True
    )
    
    if points[0]:
        point = points[0][0]
        print(f"\nSample point payload:")
        for key, value in point.payload.items():
            if key == 'text':
                print(f"  {key}: {str(value)[:100]}...")
            else:
                print(f"  {key}: {value}")

if __name__ == "__main__":
    main()