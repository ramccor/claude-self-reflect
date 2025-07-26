#!/usr/bin/env python3
"""
Import the current Claude conversation for testing.
This creates a mock conversation in the claude-self-reflection project collection.
"""

import json
import hashlib
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer

# Configuration
QDRANT_URL = "http://localhost:6333"
PROJECT_NAME = "claude-self-reflection"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def get_collection_name(project_name: str) -> str:
    """Get collection name for isolated project."""
    project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
    return f"conv_{project_hash}"

def create_test_conversation():
    """Create test conversation about our current discussion."""
    messages = [
        {
            "role": "user",
            "content": "Review the current project and give me an adversarial take on using Qdrant instead of Neo4j"
        },
        {
            "role": "assistant", 
            "content": "I'll analyze your memento-stack project and provide an adversarial perspective on migrating from Neo4j to Qdrant..."
        },
        {
            "role": "user",
            "content": "ok should we then archive existing project or work of a feature branch"
        },
        {
            "role": "assistant",
            "content": "I recommend working on a feature branch. This allows you to keep the Neo4j implementation as a fallback..."
        },
        {
            "role": "user",
            "content": "hold, roocode uses openai embedding is it better"
        },
        {
            "role": "assistant",
            "content": "Yes, OpenAI embeddings are generally superior for production use. Let me redesign the embedding service..."
        },
        {
            "role": "user",
            "content": "claude code conversations are per project - which means that mixing conversations between projects can be disastrous"
        },
        {
            "role": "assistant",
            "content": "You're absolutely right - this is a critical insight. Claude Code conversations are indeed per-project, and mixing them could be disastrous. Let me propose a project isolation strategy..."
        }
    ]
    
    # Create chunks from messages
    chunks = []
    for i in range(0, len(messages), 2):
        chunk_messages = messages[i:i+2]
        conversation_text = "\n\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in chunk_messages
        ])
        
        chunk_id = hashlib.md5(f"test_conversation_{i}".encode()).hexdigest()
        chunks.append({
            'id': chunk_id,
            'text': conversation_text,
            'metadata': {
                'project_id': PROJECT_NAME,
                'project_name': PROJECT_NAME,
                'conversation_id': 'test_current_session',
                'chunk_index': i // 2,
                'message_count': len(chunk_messages),
                'start_role': chunk_messages[0]['role'],
                'timestamp': datetime.now().isoformat(),
                'file_path': f'/logs/{PROJECT_NAME}/test_current_session.jsonl'
            }
        })
    
    return chunks

def main():
    """Import test conversation to Qdrant."""
    print(f"Importing test conversation for project: {PROJECT_NAME}")
    
    # Initialize clients
    client = QdrantClient(url=QDRANT_URL)
    encoder = SentenceTransformer(EMBEDDING_MODEL)
    
    # Get collection name
    collection_name = get_collection_name(PROJECT_NAME)
    print(f"Using collection: {collection_name}")
    
    # Create collection if it doesn't exist
    try:
        client.get_collection(collection_name)
        print(f"Collection {collection_name} already exists")
    except:
        print(f"Creating collection {collection_name}")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=384,  # all-MiniLM-L6-v2 dimension
                distance=Distance.COSINE
            )
        )
    
    # Create test conversation chunks
    chunks = create_test_conversation()
    print(f"Created {len(chunks)} conversation chunks")
    
    # Generate embeddings
    texts = [chunk['text'] for chunk in chunks]
    embeddings = encoder.encode(texts)
    
    # Create points
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        points.append(
            PointStruct(
                id=chunk['id'],
                vector=embedding.tolist(),
                payload={
                    'text': chunk['text'],
                    **chunk['metadata']
                }
            )
        )
    
    # Upload to Qdrant
    client.upsert(
        collection_name=collection_name,
        points=points
    )
    
    print(f"Successfully imported {len(points)} points to {collection_name}")
    
    # Verify by counting
    count = client.get_collection(collection_name).points_count
    print(f"Collection now contains {count} total points")

if __name__ == "__main__":
    main()