#!/usr/bin/env python3
"""
Import Claude conversation logs with project isolation support.
Each project gets its own collection for complete isolation.
"""

import json
import os
import glob
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue
)
from sentence_transformers import SentenceTransformer

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
LOGS_DIR = os.getenv("LOGS_DIR", "/logs")
STATE_FILE = os.getenv("STATE_FILE", "/config/imported-files.json")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
ISOLATION_MODE = os.getenv("ISOLATION_MODE", "isolated")  # isolated, shared, hybrid

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProjectAwareImporter:
    def __init__(self):
        """Initialize the importer with Qdrant client and embedding model."""
        self.client = QdrantClient(url=QDRANT_URL)
        self.encoder = SentenceTransformer(EMBEDDING_MODEL)
        self.imported_files = self.load_state()
        self.project_collections: Set[str] = set()
        
    def load_state(self) -> Dict[str, Set[str]]:
        """Load the set of already imported files per project."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    # Convert to per-project tracking
                    if isinstance(data.get('files'), list):
                        # Legacy format - convert to new format
                        return {'_legacy': set(data['files'])}
                    else:
                        # New format with per-project tracking
                        return {k: set(v) for k, v in data.get('projects', {}).items()}
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        return {}
    
    def save_state(self):
        """Save the set of imported files per project."""
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump({
                'projects': {k: list(v) for k, v in self.imported_files.items()},
                'last_updated': datetime.now().isoformat(),
                'mode': ISOLATION_MODE
            }, f, indent=2)
    
    def get_collection_name(self, project_name: str) -> str:
        """Get collection name based on isolation mode."""
        if ISOLATION_MODE == "isolated":
            # Create project-specific collection name
            project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
            return f"conv_{project_hash}"
        else:
            # Shared collection mode
            return "conversations"
    
    def setup_collection(self, project_name: str):
        """Create or update the Qdrant collection for a project."""
        collection_name = self.get_collection_name(project_name)
        
        # Skip if already set up in this session
        if collection_name in self.project_collections:
            return collection_name
        
        collections = self.client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if not exists:
            logger.info(f"Creating collection: {collection_name} for project: {project_name}")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=384,  # all-MiniLM-L6-v2 dimension
                    distance=Distance.COSINE
                )
            )
        else:
            logger.info(f"Collection {collection_name} already exists for project: {project_name}")
        
        self.project_collections.add(collection_name)
        return collection_name
    
    def extract_project_name(self, file_path: str) -> str:
        """Extract project name from file path."""
        # Expected path: /logs/<project-name>/<conversation-id>.jsonl
        parts = file_path.split('/')
        if len(parts) >= 3 and parts[-2] != 'logs':
            return parts[-2]
        return 'unknown'
    
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
            project_id = self.extract_project_name(chunk_messages[0]['file_path'])
            conversation_id = os.path.basename(chunk_messages[0]['file_path']).replace('.jsonl', '')
            
            chunks.append({
                'id': hashlib.md5(f"{chunk_messages[0]['file_path']}_{i}".encode()).hexdigest(),
                'text': conversation_text,
                'metadata': {
                    'project_id': project_id,
                    'project_name': project_id,  # Add both for compatibility
                    'conversation_id': conversation_id,
                    'chunk_index': i // chunk_size,
                    'message_count': len(chunk_messages),
                    'start_role': chunk_messages[0]['role'],
                    'timestamp': chunk_messages[0]['timestamp'],
                    'file_path': chunk_messages[0]['file_path']
                }
            })
        
        return chunks
    
    def import_to_qdrant(self, chunks: List[Dict[str, Any]], collection_name: str):
        """Import conversation chunks to a specific Qdrant collection."""
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
                collection_name=collection_name,
                points=batch
            )
            logger.info(f"Uploaded batch of {len(batch)} points to {collection_name}")
    
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
        """Main import process with project isolation."""
        logger.info(f"Starting conversation import to Qdrant (mode: {ISOLATION_MODE})")
        
        # Find files to import
        all_files = self.find_recent_files()
        logger.info(f"Found {len(all_files)} total files")
        
        # Group files by project
        files_by_project: Dict[str, List[str]] = {}
        for file_path in all_files:
            project_name = self.extract_project_name(file_path)
            if project_name not in files_by_project:
                files_by_project[project_name] = []
            files_by_project[project_name].append(file_path)
        
        logger.info(f"Found {len(files_by_project)} projects to process")
        
        total_chunks = 0
        for project_name, project_files in files_by_project.items():
            logger.info(f"\nProcessing project: {project_name}")
            
            # Get imported files for this project
            project_imported = self.imported_files.get(project_name, set())
            new_files = [f for f in project_files if f not in project_imported]
            
            if not new_files:
                logger.info(f"No new files for project {project_name}")
                continue
            
            logger.info(f"Found {len(new_files)} new files for project {project_name}")
            
            # Setup collection for this project
            collection_name = self.setup_collection(project_name)
            
            project_chunks = 0
            for file_path in new_files:
                logger.info(f"Processing: {file_path}")
                
                # Extract messages
                messages = self.process_jsonl_file(file_path)
                if not messages:
                    logger.warning(f"No messages found in {file_path}")
                    continue
                
                # Create conversation chunks
                chunks = self.create_conversation_chunks(messages)
                
                # Import to project-specific collection
                self.import_to_qdrant(chunks, collection_name)
                
                # Mark file as imported for this project
                if project_name not in self.imported_files:
                    self.imported_files[project_name] = set()
                self.imported_files[project_name].add(file_path)
                self.save_state()
                
                project_chunks += len(chunks)
                logger.info(f"Imported {len(chunks)} chunks from {file_path}")
            
            total_chunks += project_chunks
            logger.info(f"Project {project_name} complete: {project_chunks} chunks imported")
        
        logger.info(f"\nImport complete: {total_chunks} total chunks imported")
        
        # Show collection summary
        logger.info("\nCollection summary:")
        collections = self.client.get_collections().collections
        for collection in collections:
            if collection.name.startswith('conv_') or collection.name == 'conversations':
                count = self.client.get_collection(collection.name).points_count
                logger.info(f"  {collection.name}: {count} points")

def main():
    """Entry point for the importer."""
    importer = ProjectAwareImporter()
    importer.run()

if __name__ == "__main__":
    main()