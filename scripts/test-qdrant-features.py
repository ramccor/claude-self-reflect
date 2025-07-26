#!/usr/bin/env python3
"""Test what Qdrant features are available in the current client."""

import asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
import inspect

async def test_features():
    """Check available Qdrant features."""
    
    print("Qdrant Client Features Check")
    print("=" * 60)
    
    # Check models
    print("\nAvailable Expression Models:")
    expression_models = [name for name in dir(models) if 'Expression' in name or 'Decay' in name]
    for model in sorted(expression_models):
        print(f"  - {model}")
    
    print("\nAvailable Query Models:")
    query_models = [name for name in dir(models) if 'Query' in name or 'Formula' in name]
    for model in sorted(query_models):
        print(f"  - {model}")
    
    # Check AsyncQdrantClient methods
    client = AsyncQdrantClient(url="http://localhost:6333")
    
    print("\nAsyncQdrantClient query methods:")
    query_methods = [name for name in dir(client) if 'query' in name.lower()]
    for method in sorted(query_methods):
        if not method.startswith('_'):
            print(f"  - {method}")
            # Get method signature
            try:
                sig = inspect.signature(getattr(client, method))
                print(f"    Signature: {sig}")
            except:
                pass
    
    print("\n" + "=" * 60)
    print("Note: Qdrant's decay functions may require newer server/client versions")
    print("Current approach: Client-side calculation works with all versions")

if __name__ == "__main__":
    asyncio.run(test_features())