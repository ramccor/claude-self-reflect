#!/usr/bin/env python3
import os
import hashlib
from qdrant_client import QdrantClient

# Initialize client
client = QdrantClient(url="http://localhost:6333")

# Show what collection the MCP would use
isolation_mode = os.environ.get('ISOLATION_MODE', 'shared')
current_dir = os.path.basename(os.getcwd())

print(f"Current directory: {current_dir}")
print(f"Isolation mode: {isolation_mode}")

# Calculate project hash
project_hash = hashlib.md5(current_dir.encode()).hexdigest()[:8]
expected_collection = f"conv_{project_hash}" if isolation_mode == 'isolated' else 'conversations'

print(f"\nExpected collection name: {expected_collection}")
print(f"Project hash: {project_hash}")

# Check if collection exists
try:
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]
    print(f"\nAvailable collections: {collection_names}")
    
    if expected_collection in collection_names:
        print(f"\n✓ Collection '{expected_collection}' exists")
        
        # Get collection info
        collection_info = client.get_collection(expected_collection)
        print(f"  Vector size: {collection_info.config.params.vectors.size}")
        print(f"  Points count: {collection_info.points_count}")
        
        # Sample some points
        scroll_result = client.scroll(
            collection_name=expected_collection,
            limit=3,
            with_payload=True,
            with_vector=False
        )
        
        if scroll_result[0]:
            print(f"\nSample points from '{expected_collection}':")
            for i, point in enumerate(scroll_result[0][:3]):
                print(f"\n  Point {i+1}:")
                print(f"    ID: {point.id}")
                if point.payload:
                    print(f"    Project: {point.payload.get('project_id', 'N/A')}")
                    text = point.payload.get('text', '')
                    print(f"    Text preview: {text[:100]}...")
    else:
        print(f"\n✗ Collection '{expected_collection}' does not exist")
        print(f"  MCP server will likely fail to find conversations")
        
except Exception as e:
    print(f"Error: {e}")

# Test what collection MCP is actually using based on environment
print("\n" + "="*50)
print("MCP Server Configuration:")
print(f"ISOLATION_MODE={os.environ.get('ISOLATION_MODE', 'shared')}")
print(f"COLLECTION_NAME={os.environ.get('COLLECTION_NAME', 'conversations')}")

# Since MCP is configured with ISOLATION_MODE=shared, it will use 'conversations'
print("\nBased on mcp.json configuration, MCP server will use: 'conversations' collection")