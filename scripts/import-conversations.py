#!/usr/bin/env python3
"""
Import Claude conversation logs from JSONL files into Qdrant vector database.
Simplified version focusing on semantic search without complex entity extraction.
"""

import json
import os
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue
)
from sentence_transformers import SentenceTransformer
import hashlib

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "conversations")
LOGS_DIR = os.getenv("LOGS_DIR", "/logs")
STATE_FILE = os.getenv("STATE_FILE", "/config/imported-files.json")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConversationImporter:
    def __init__(self):
        """Initialize the importer with Qdrant client and embedding model."""
        self.client = QdrantClient(url=QDRANT_URL)
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)
        self.imported_files = self.load_state()
        
    def load_state(self) -> set:
        """Load the set of already imported files."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    return set(data.get('files', []))
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        return set()
    
    def save_state(self):
        """Save the set of imported files."""
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'files': list(self.imported_files),
                'last_updated': datetime.now().isoformat()
            }, f)
    
    def setup_collection(self):
        """Create or update the Qdrant collection."""
        collections = self.client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        
        if not exists:
            logger.info(f"Creating collection: {COLLECTION_NAME}")
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=384,  # all-MiniLM-L6-v2 dimension
                    distance=Distance.COSINE
                )
            )
        else:
            logger.info(f"Collection {COLLECTION_NAME} already exists")
    
    def process_jsonl_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract messages from a JSONL file."""
        messages = []
        
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line.strip())
                        
                        # Extract message if present
                        if 'message' in data and data['message']:
                            msg = data['message']
                            if 'role' in msg and 'content' in msg:
                                # Handle content that might be an object
                                content = msg['content']
                                if isinstance(content, dict):
                                    content = content.get('text', json.dumps(content))
                                
                                # Create message document
                                messages.append({
                                    'role': msg['role'],
                                    'content': content,
                                    'file_path': file_path,
                                    'line_number': line_num,
                                    'timestamp': data.get('timestamp', datetime.now().isoformat())
                                })
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse line {line_num} in {file_path}")
                    except Exception as e:
                        logger.error(f"Error processing line {line_num} in {file_path}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
        
        return messages
    
    def create_conversation_chunks(self, messages: List[Dict[str, Any]], chunk_size: int = 5) -> List[Dict[str, Any]]:
        """Group messages into conversation chunks for better context."""
        chunks = []
        
        for i in range(0, len(messages), chunk_size):
            chunk_messages = messages[i:i + chunk_size]
            
            # Create a conversation summary
            conversation_text = "\n\n".join([
                f"{msg['role'].upper()}: {msg['content'][:500]}..."
                if len(msg['content']) > 500 else f"{msg['role'].upper()}: {msg['content']}"
                for msg in chunk_messages
            ])
            
            # Extract metadata
            project_id = os.path.basename(os.path.dirname(os.path.dirname(chunk_messages[0]['file_path'])))
            conversation_id = os.path.basename(chunk_messages[0]['file_path']).replace('.jsonl', '')
            
            chunks.append({
                'id': hashlib.md5(f"{chunk_messages[0]['file_path']}_{i}".encode()).hexdigest(),
                'text': conversation_text,
                'metadata': {
                    'project_id': project_id,
                    'conversation_id': conversation_id,
                    'chunk_index': i // chunk_size,
                    'message_count': len(chunk_messages),
                    'start_role': chunk_messages[0]['role'],
                    'timestamp': chunk_messages[0]['timestamp'],
                    'file_path': chunk_messages[0]['file_path']
                }
            })
        
        return chunks
    
    def import_to_qdrant(self, chunks: List[Dict[str, Any]]):
        """Import conversation chunks to Qdrant."""
        if not chunks:
            return
        
        # Generate embeddings
        texts = [chunk['text'] for chunk in chunks]
        embeddings = self.encoder.encode(texts, show_progress_bar=True)
        
        # Create points for Qdrant
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
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
        
        # Upload to Qdrant in batches
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i:i + BATCH_SIZE]
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=batch
            )
            logger.info(f"Uploaded batch of {len(batch)} points")
    
    def find_recent_files(self, days: int = 30) -> List[str]:
        """Find JSONL files modified in the last N days."""
        cutoff_time = datetime.now() - timedelta(days=days)
        pattern = os.path.join(LOGS_DIR, "**", "*.jsonl")
        
        recent_files = []
        for file_path in glob.glob(pattern, recursive=True):
            try:
                mtime = os.path.getmtime(file_path)
                if datetime.fromtimestamp(mtime) >= cutoff_time:
                    recent_files.append(file_path)
            except Exception as e:
                logger.error(f"Error checking file {file_path}: {e}")
        
        return recent_files
    
    def run(self):
        """Main import process."""
        logger.info("Starting conversation import to Qdrant")
        
        # Setup collection
        self.setup_collection()
        
        # Find files to import
        all_files = self.find_recent_files()
        new_files = [f for f in all_files if f not in self.imported_files]
        
        logger.info(f"Found {len(all_files)} total files, {len(new_files)} new files to import")
        
        total_chunks = 0
        for file_path in new_files:
            logger.info(f"Processing: {file_path}")
            
            # Extract messages
            messages = self.process_jsonl_file(file_path)
            if not messages:
                logger.warning(f"No messages found in {file_path}")
                continue
            
            # Create conversation chunks
            chunks = self.create_conversation_chunks(messages)
            
            # Import to Qdrant
            self.import_to_qdrant(chunks)
            
            # Mark file as imported
            self.imported_files.add(file_path)
            self.save_state()
            
            total_chunks += len(chunks)
            logger.info(f"Imported {len(chunks)} chunks from {file_path}")
        
        logger.info(f"Import complete: {total_chunks} total chunks imported from {len(new_files)} files")

def main():
    """Entry point for the importer."""
    importer = ConversationImporter()
    importer.run()

if __name__ == "__main__":
    main()