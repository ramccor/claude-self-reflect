#!/usr/bin/env python3
"""
Import a single project's conversations to Qdrant.
This script processes one project at a time to avoid memory issues.
"""

import json
import os
import sys
import glob
import hashlib
from datetime import datetime
from typing import List, Dict, Any
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
STATE_FILE = os.getenv("STATE_FILE", "./config-isolated/imported-files.json")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 50  # Reduced batch size for memory efficiency
CHUNK_SIZE = 5   # Messages per chunk

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SingleProjectImporter:
    def __init__(self, project_path: str):
        """Initialize importer for a single project."""
        self.project_path = project_path
        self.project_name = os.path.basename(project_path)
        self.client = QdrantClient(url=QDRANT_URL)
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)
        self.imported_files = self.load_state()
        
    def load_state(self) -> Dict[str, List[str]]:
        """Load import state."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get('projects', {})
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        return {}
    
    def save_state(self):
        """Save import state."""
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        
        # Load existing state to preserve other projects
        existing = {}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    existing = json.load(f)
            except:
                pass
        
        # Update with current project
        if 'projects' not in existing:
            existing['projects'] = {}
        existing['projects'][self.project_name] = self.imported_files.get(self.project_name, [])
        existing['last_updated'] = datetime.now().isoformat()
        existing['mode'] = 'isolated'
        
        with open(STATE_FILE, 'w') as f:
            json.dump(existing, f, indent=2)
    
    def get_collection_name(self) -> str:
        """Get collection name for this project."""
        project_hash = hashlib.md5(self.project_name.encode()).hexdigest()[:8]
        return f"conv_{project_hash}"
    
    def setup_collection(self):
        """Create or verify collection exists."""
        collection_name = self.get_collection_name()
        
        collections = self.client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if not exists:
            logger.info(f"Creating collection: {collection_name}")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=384,  # all-MiniLM-L6-v2 dimension
                    distance=Distance.COSINE
                )
            )
        else:
            logger.info(f"Collection {collection_name} already exists")
        
        return collection_name
    
    def process_jsonl_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract messages from a JSONL file."""
        messages = []
        
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line.strip())
                        
                        if 'message' in data and data['message']:
                            msg = data['message']
                            if 'role' in msg and 'content' in msg:
                                content = msg['content']
                                if isinstance(content, dict):
                                    content = content.get('text', json.dumps(content))
                                
                                messages.append({
                                    'role': msg['role'],
                                    'content': content,
                                    'file_path': file_path,
                                    'line_number': line_num,
                                    'timestamp': data.get('timestamp', datetime.now().isoformat())
                                })
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.debug(f"Error processing line {line_num}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
        
        return messages
    
    def create_conversation_chunks(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group messages into conversation chunks."""
        chunks = []
        
        for i in range(0, len(messages), CHUNK_SIZE):
            chunk_messages = messages[i:i + CHUNK_SIZE]
            
            conversation_text = "\n\n".join([
                f"{msg['role'].upper()}: {msg['content'][:500]}..."
                if len(msg['content']) > 500 else f"{msg['role'].upper()}: {msg['content']}"
                for msg in chunk_messages
            ])
            
            conversation_id = os.path.basename(chunk_messages[0]['file_path']).replace('.jsonl', '')
            
            chunks.append({
                'id': hashlib.md5(f"{chunk_messages[0]['file_path']}_{i}".encode()).hexdigest(),
                'text': conversation_text,
                'metadata': {
                    'project_id': self.project_name,
                    'project_name': self.project_name,
                    'conversation_id': conversation_id,
                    'chunk_index': i // CHUNK_SIZE,
                    'message_count': len(chunk_messages),
                    'start_role': chunk_messages[0]['role'],
                    'timestamp': chunk_messages[0]['timestamp'],
                    'file_path': chunk_messages[0]['file_path']
                }
            })
        
        return chunks
    
    def import_to_qdrant(self, chunks: List[Dict[str, Any]], collection_name: str):
        """Import chunks to Qdrant with memory-efficient batching."""
        if not chunks:
            return
        
        # Process in smaller batches to avoid memory issues
        for batch_start in range(0, len(chunks), BATCH_SIZE):
            batch_chunks = chunks[batch_start:batch_start + BATCH_SIZE]
            
            # Generate embeddings for this batch
            texts = [chunk['text'] for chunk in batch_chunks]
            embeddings = self.encoder.encode(texts, show_progress_bar=False)
            
            # Create points
            points = []
            for chunk, embedding in zip(batch_chunks, embeddings):
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
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )
            logger.info(f"Uploaded batch of {len(points)} points")
            
            # Clear memory
            del texts, embeddings, points
    
    def import_project(self):
        """Import all conversations for this project."""
        logger.info(f"Importing project: {self.project_name}")
        
        # Find all JSONL files
        pattern = os.path.join(self.project_path, "*.jsonl")
        all_files = glob.glob(pattern)
        
        if not all_files:
            logger.warning(f"No JSONL files found in {self.project_path}")
            return
        
        # Get already imported files for this project
        project_imported = set(self.imported_files.get(self.project_name, []))
        
        # Convert to relative paths for comparison
        new_files = []
        for f in all_files:
            rel_path = f.replace(os.path.expanduser("~/.claude/projects"), "/logs")
            if rel_path not in project_imported:
                new_files.append((f, rel_path))
        
        if not new_files:
            logger.info(f"All files already imported for {self.project_name}")
            return
        
        logger.info(f"Found {len(new_files)} new files to import")
        
        # Setup collection
        collection_name = self.setup_collection()
        
        # Process files one by one
        total_chunks = 0
        for file_path, rel_path in new_files:
            logger.info(f"Processing: {os.path.basename(file_path)}")
            
            # Extract messages
            messages = self.process_jsonl_file(file_path)
            if not messages:
                logger.warning(f"No messages found in {file_path}")
                continue
            
            # Create chunks
            chunks = self.create_conversation_chunks(messages)
            
            # Import to Qdrant
            self.import_to_qdrant(chunks, collection_name)
            
            # Update state after each file
            if self.project_name not in self.imported_files:
                self.imported_files[self.project_name] = []
            self.imported_files[self.project_name].append(rel_path)
            self.save_state()
            
            total_chunks += len(chunks)
            logger.info(f"Imported {len(chunks)} chunks from {os.path.basename(file_path)}")
        
        # Final summary
        count = self.client.get_collection(collection_name).points_count
        logger.info(f"Project complete: {total_chunks} chunks imported, {count} total points in collection")

def main():
    if len(sys.argv) != 2:
        print("Usage: python import-single-project.py <project_path>")
        print("Example: python import-single-project.py ~/.claude/projects/my-project")
        sys.exit(1)
    
    project_path = sys.argv[1]
    if not os.path.exists(project_path):
        logger.error(f"Project path does not exist: {project_path}")
        sys.exit(1)
    
    importer = SingleProjectImporter(project_path)
    importer.import_project()

if __name__ == "__main__":
    main()