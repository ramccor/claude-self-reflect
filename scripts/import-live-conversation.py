#!/usr/bin/env python3
"""Import the currently active conversation file."""

import os
import sys
import json
import hashlib
from datetime import datetime, timedelta
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import backoff
import requests

# Configuration
QDRANT_URL = "http://localhost:6333"
VOYAGE_API_KEY = os.getenv("VOYAGE_KEY", "pa-wdTYGObaxhs-XFKX2r7WCczRwEVNb9eYMTSO3yrQhZI")
VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def generate_embedding(text):
    """Generate embedding using Voyage AI."""
    headers = {
        "Authorization": f"Bearer {VOYAGE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        VOYAGE_API_URL,
        headers=headers,
        json={
            "input": [text],
            "model": "voyage-3-large"
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Voyage API error: {response.status_code} - {response.text}")
        
    return response.json()["data"][0]["embedding"]

def import_conversation(file_path):
    """Import a single conversation file."""
    client = QdrantClient(url=QDRANT_URL)
    
    # Determine collection name
    project_path = "/Users/ramakrishnanannaswamy/memento-stack"
    project_hash = hashlib.md5(project_path.encode()).hexdigest()[:8]
    collection_name = f"conv_{project_hash}_voyage"
    
    print(f"Importing to collection: {collection_name}")
    
    # Ensure collection exists
    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
        )
    
    # Read recent messages (last 2 hours)
    from datetime import timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    points_to_import = []
    
    with open(file_path, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)
                timestamp_str = entry.get('timestamp', '')
                
                # Parse timestamp
                if timestamp_str:
                    # Convert ISO format to datetime
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    
                    # Only import recent entries
                    if timestamp > cutoff:
                        # Extract message content
                        message = entry.get('message', {})
                        content = message.get('content', [])
                        
                        # Extract text from content
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                text_parts.append(item.get('text', ''))
                        
                        if text_parts:
                            text = ' '.join(text_parts)
                            
                            # Create unique ID
                            point_id = hashlib.md5(f"{entry.get('uuid', '')}_{timestamp_str}".encode()).hexdigest()
                            
                            # Generate embedding
                            print(f"Generating embedding for entry from {timestamp_str[:19]}")
                            try:
                                embedding = generate_embedding(text[:8000])  # Limit text length
                                
                                points_to_import.append(
                                    PointStruct(
                                        id=point_id,
                                        vector=embedding,
                                        payload={
                                            "text": text[:2000],
                                            "timestamp": timestamp.timestamp(),
                                            "role": message.get('role', 'unknown'),
                                            "conversation_id": entry.get('sessionId', ''),
                                            "project": project_path
                                        }
                                    )
                                )
                                
                                # Import in batches
                                if len(points_to_import) >= 10:
                                    client.upsert(
                                        collection_name=collection_name,
                                        points=points_to_import
                                    )
                                    print(f"Imported batch of {len(points_to_import)} points")
                                    points_to_import = []
                                    
                            except Exception as e:
                                print(f"Error generating embedding: {e}")
                                
            except json.JSONDecodeError:
                continue
                
    # Import remaining points
    if points_to_import:
        client.upsert(
            collection_name=collection_name,
            points=points_to_import
        )
        print(f"Imported final batch of {len(points_to_import)} points")
    
    # Check collection status
    info = client.get_collection(collection_name)
    print(f"\nCollection {collection_name} now has {info.points_count} points")

def main():
    file_path = os.path.expanduser("~/.claude/projects/-Users-ramakrishnanannaswamy-memento-stack/2bb5f256-bc0a-4a29-8807-f796a463fade.jsonl")
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
        
    print(f"Importing live conversation from: {file_path}")
    import_conversation(file_path)
    print("\nImport complete!")

if __name__ == "__main__":
    main()