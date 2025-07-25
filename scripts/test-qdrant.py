#!/usr/bin/env python3
"""
Test script to verify Qdrant functionality.
"""

import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "test_collection"

def test_qdrant():
    """Test basic Qdrant operations."""
    client = QdrantClient(url=QDRANT_URL)
    encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    
    # Create test collection
    logger.info("Creating test collection...")
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
    )
    
    # Test data
    test_conversations = [
        "We discussed switching from Neo4j to Qdrant for better performance",
        "The user asked about implementing a chat memory system",
        "We analyzed the complexity of graph databases versus vector databases",
        "Qdrant provides simple semantic search without entity extraction"
    ]
    
    # Generate embeddings and store
    logger.info("Generating embeddings and storing...")
    embeddings = encoder.encode(test_conversations)
    
    points = [
        PointStruct(
            id=i,
            vector=embedding.tolist(),
            payload={"text": text}
        )
        for i, (text, embedding) in enumerate(zip(test_conversations, embeddings))
    ]
    
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    
    # Test search
    logger.info("Testing semantic search...")
    query = "chat memory implementation"
    query_vector = encoder.encode(query).tolist()
    
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=3
    )
    
    logger.info(f"\nSearch results for '{query}':")
    for result in results:
        logger.info(f"Score: {result.score:.3f} - {result.payload['text']}")
    
    # Cleanup
    client.delete_collection(collection_name=COLLECTION_NAME)
    logger.info("\nTest completed successfully!")

if __name__ == "__main__":
    test_qdrant()