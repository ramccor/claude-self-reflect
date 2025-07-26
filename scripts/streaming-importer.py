#!/usr/bin/env python3
"""
Memory-efficient streaming importer for Claude conversations.
Processes JSONL files line-by-line without loading entire files into memory.
"""

import json
import os
import sys
import gc
import hashlib
import psutil
from datetime import datetime
from typing import Generator, Dict, Any, List, Optional
import logging
from contextlib import contextmanager
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, UpdateStatus
from sentence_transformers import SentenceTransformer
import numpy as np

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
STATE_FILE = os.getenv("STATE_FILE", "./config-isolated/imported-files.json")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))  # Smaller batches for memory efficiency
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "5"))
MAX_MEMORY_MB = int(os.getenv("MAX_MEMORY_MB", "400"))  # Memory limit in MB
CHECKPOINT_INTERVAL = int(os.getenv("CHECKPOINT_INTERVAL", "100"))  # Save progress every N chunks

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

class MemoryMonitor:
    """Monitor memory usage and enforce limits."""
    
    def __init__(self, max_memory_mb: int):
        self.max_memory_mb = max_memory_mb
        self.process = psutil.Process()
        self.initial_memory = self.get_memory_usage()
        
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def check_memory(self) -> bool:
        """Check if memory usage is within limits."""
        current = self.get_memory_usage()
        if current > self.max_memory_mb:
            logger.warning(f"Memory usage ({current:.1f}MB) exceeds limit ({self.max_memory_mb}MB)")
            return False
        return True
    
    def log_memory(self, context: str = ""):
        """Log current memory usage."""
        current = self.get_memory_usage()
        delta = current - self.initial_memory
        logger.debug(f"Memory usage {context}: {current:.1f}MB (Δ{delta:+.1f}MB)")

class StreamingImporter:
    def __init__(self):
        """Initialize the streaming importer."""
        self.client = QdrantClient(url=QDRANT_URL, timeout=30)
        self.encoder = None  # Lazy load to save memory
        self.memory_monitor = MemoryMonitor(MAX_MEMORY_MB)
        self.state = self.load_state()
        self.checkpoints = {}
        
    def load_state(self) -> Dict[str, Any]:
        """Load import state from file."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        return {"projects": {}, "checkpoints": {}}
    
    def save_state(self):
        """Save import state to file."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            self.state["last_updated"] = datetime.now().isoformat()
            self.state["checkpoints"] = self.checkpoints
            
            # Write to temp file first for atomicity
            temp_file = f"{STATE_FILE}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            os.rename(temp_file, STATE_FILE)
            
            logger.debug("State saved successfully")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    @contextmanager
    def get_encoder(self):
        """Context manager for encoder to ensure proper cleanup."""
        try:
            if self.encoder is None:
                logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
                self.encoder = SentenceTransformer(EMBEDDING_MODEL)
            yield self.encoder
        finally:
            # Force garbage collection after encoding
            gc.collect()
    
    def get_collection_name(self, project_name: str) -> str:
        """Generate collection name for project."""
        project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
        return f"conv_{project_hash}"
    
    def ensure_collection(self, collection_name: str) -> bool:
        """Ensure collection exists."""
        try:
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
            return True
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
            return False
    
    def stream_jsonl_messages(self, file_path: str) -> Generator[Dict[str, Any], None, None]:
        """Stream messages from JSONL file line by line."""
        line_num = 0
        checkpoint_key = hashlib.md5(file_path.encode()).hexdigest()
        start_line = self.checkpoints.get(checkpoint_key, 0)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # Skip to checkpoint if resuming
                    if line_num <= start_line:
                        continue
                    
                    if not line.strip():
                        continue
                    
                    try:
                        data = json.loads(line)
                        if 'message' in data and data['message']:
                            msg = data['message']
                            if 'role' in msg and 'content' in msg:
                                content = msg['content']
                                
                                # Handle different content formats
                                if isinstance(content, list):
                                    # Extract text from content blocks
                                    text_parts = []
                                    for block in content:
                                        if isinstance(block, dict) and block.get('type') == 'text':
                                            text_parts.append(block.get('text', ''))
                                    content = ' '.join(text_parts)
                                elif isinstance(content, dict):
                                    content = content.get('text', json.dumps(content))
                                
                                if content:
                                    yield {
                                        'role': msg['role'],
                                        'content': content,
                                        'line_number': line_num,
                                        'timestamp': data.get('timestamp', datetime.now().isoformat())
                                    }
                    
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.debug(f"Skipping line {line_num}: {e}")
                        continue
                    
                    # Update checkpoint periodically
                    if line_num % CHECKPOINT_INTERVAL == 0:
                        self.checkpoints[checkpoint_key] = line_num
                        self.save_state()
                        
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
        finally:
            # Clear checkpoint on completion
            if checkpoint_key in self.checkpoints:
                del self.checkpoints[checkpoint_key]
    
    def create_chunks_streaming(self, file_path: str, project_name: str) -> Generator[Dict[str, Any], None, None]:
        """Create conversation chunks from streaming messages."""
        conversation_id = os.path.basename(file_path).replace('.jsonl', '')
        buffer = []
        chunk_index = 0
        
        for message in self.stream_jsonl_messages(file_path):
            buffer.append(message)
            
            if len(buffer) >= CHUNK_SIZE:
                # Process buffer into chunk
                conversation_text = "\n\n".join([
                    f"{msg['role'].upper()}: {msg['content'][:500]}..."
                    if len(msg['content']) > 500 else f"{msg['role'].upper()}: {msg['content']}"
                    for msg in buffer
                ])
                
                chunk_id = hashlib.md5(
                    f"{file_path}_{chunk_index}_{buffer[0]['line_number']}".encode()
                ).hexdigest()
                
                yield {
                    'id': chunk_id,
                    'text': conversation_text,
                    'metadata': {
                        'project_id': project_name,
                        'project_name': project_name,
                        'conversation_id': conversation_id,
                        'chunk_index': chunk_index,
                        'message_count': len(buffer),
                        'start_role': buffer[0]['role'],
                        'timestamp': buffer[0]['timestamp'],
                        'file_path': file_path
                    }
                }
                
                chunk_index += 1
                buffer = []
                
                # Check memory after each chunk
                if not self.memory_monitor.check_memory():
                    logger.warning("Memory limit reached, forcing garbage collection")
                    gc.collect()
        
        # Process remaining messages
        if buffer:
            conversation_text = "\n\n".join([
                f"{msg['role'].upper()}: {msg['content'][:500]}..."
                if len(msg['content']) > 500 else f"{msg['role'].upper()}: {msg['content']}"
                for msg in buffer
            ])
            
            chunk_id = hashlib.md5(
                f"{file_path}_{chunk_index}_{buffer[0]['line_number']}".encode()
            ).hexdigest()
            
            yield {
                'id': chunk_id,
                'text': conversation_text,
                'metadata': {
                    'project_id': project_name,
                    'project_name': project_name,
                    'conversation_id': conversation_id,
                    'chunk_index': chunk_index,
                    'message_count': len(buffer),
                    'start_role': buffer[0]['role'],
                    'timestamp': buffer[0]['timestamp'],
                    'file_path': file_path
                }
            }
    
    def import_file_streaming(self, file_path: str, project_name: str, collection_name: str) -> int:
        """Import a single file using streaming approach."""
        logger.info(f"Processing file: {os.path.basename(file_path)}")
        chunks_processed = 0
        batch_buffer = []
        
        try:
            with self.get_encoder() as encoder:
                for chunk in self.create_chunks_streaming(file_path, project_name):
                    batch_buffer.append(chunk)
                    
                    if len(batch_buffer) >= BATCH_SIZE:
                        # Process batch
                        self._upload_batch(batch_buffer, encoder, collection_name)
                        chunks_processed += len(batch_buffer)
                        batch_buffer = []
                        
                        # Log progress
                        if chunks_processed % 50 == 0:
                            self.memory_monitor.log_memory(f"after {chunks_processed} chunks")
                
                # Process remaining chunks
                if batch_buffer:
                    self._upload_batch(batch_buffer, encoder, collection_name)
                    chunks_processed += len(batch_buffer)
            
            logger.info(f"Imported {chunks_processed} chunks from {os.path.basename(file_path)}")
            return chunks_processed
            
        except Exception as e:
            logger.error(f"Failed to import file {file_path}: {e}")
            return chunks_processed
    
    def _upload_batch(self, chunks: List[Dict[str, Any]], encoder, collection_name: str):
        """Upload a batch of chunks to Qdrant."""
        try:
            # Extract texts for encoding
            texts = [chunk['text'] for chunk in chunks]
            
            # Generate embeddings
            embeddings = encoder.encode(texts, batch_size=len(texts), show_progress_bar=False)
            
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
            response = self.client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True
            )
            
            if response.status == UpdateStatus.COMPLETED:
                logger.debug(f"Uploaded batch of {len(points)} points")
            else:
                logger.warning(f"Upload response: {response}")
            
            # Clear memory
            del texts, embeddings, points
            gc.collect()
            
        except Exception as e:
            logger.error(f"Failed to upload batch: {e}")
    
    def import_project(self, project_path: str) -> Dict[str, int]:
        """Import all conversations for a project."""
        project_name = os.path.basename(project_path)
        logger.info(f"\nImporting project: {project_name}")
        
        stats = {"files": 0, "chunks": 0, "errors": 0}
        
        # Ensure collection exists
        collection_name = self.get_collection_name(project_name)
        if not self.ensure_collection(collection_name):
            stats["errors"] += 1
            return stats
        
        # Get files to import
        import os.path
        jsonl_files = []
        for file in os.listdir(project_path):
            if file.endswith('.jsonl'):
                jsonl_files.append(os.path.join(project_path, file))
        
        if not jsonl_files:
            logger.warning(f"No JSONL files found in {project_path}")
            return stats
        
        # Check already imported files
        project_state = self.state.get("projects", {}).get(project_name, [])
        
        for file_path in jsonl_files:
            rel_path = file_path.replace(os.path.expanduser("~/.claude/projects"), "/logs")
            
            if rel_path in project_state:
                logger.debug(f"Skipping already imported: {os.path.basename(file_path)}")
                continue
            
            try:
                chunks = self.import_file_streaming(file_path, project_name, collection_name)
                stats["chunks"] += chunks
                stats["files"] += 1
                
                # Update state
                if project_name not in self.state["projects"]:
                    self.state["projects"][project_name] = []
                self.state["projects"][project_name].append(rel_path)
                self.save_state()
                
            except Exception as e:
                logger.error(f"Failed to import {file_path}: {e}")
                stats["errors"] += 1
        
        # Log final stats
        try:
            count = self.client.get_collection(collection_name).points_count
            logger.info(f"Project {project_name} complete: {stats['files']} files, "
                       f"{stats['chunks']} chunks imported, {count} total points in collection")
        except:
            pass
        
        return stats
    
    def import_all_projects(self, projects_dir: str):
        """Import all projects from Claude directory."""
        logger.info(f"Starting import from: {projects_dir}")
        total_stats = {"projects": 0, "files": 0, "chunks": 0, "errors": 0}
        
        # Get all project directories
        project_dirs = []
        for item in os.listdir(projects_dir):
            path = os.path.join(projects_dir, item)
            if os.path.isdir(path):
                project_dirs.append(path)
        
        logger.info(f"Found {len(project_dirs)} projects to process")
        
        for i, project_dir in enumerate(project_dirs, 1):
            project_name = os.path.basename(project_dir)
            logger.info(f"\n[{i}/{len(project_dirs)}] Processing: {project_name}")
            
            stats = self.import_project(project_dir)
            total_stats["projects"] += 1
            total_stats["files"] += stats["files"]
            total_stats["chunks"] += stats["chunks"]
            total_stats["errors"] += stats["errors"]
            
            # Memory check between projects
            self.memory_monitor.log_memory(f"after project {i}")
            gc.collect()
        
        # Final summary
        logger.info("\n" + "="*50)
        logger.info("IMPORT COMPLETE")
        logger.info(f"Projects processed: {total_stats['projects']}")
        logger.info(f"Files imported: {total_stats['files']}")
        logger.info(f"Chunks created: {total_stats['chunks']}")
        logger.info(f"Errors encountered: {total_stats['errors']}")
        logger.info("="*50)

def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Import specific project
        project_path = sys.argv[1]
        if not os.path.exists(project_path):
            logger.error(f"Project path does not exist: {project_path}")
            sys.exit(1)
        
        importer = StreamingImporter()
        importer.import_project(project_path)
    else:
        # Import all projects
        projects_dir = os.path.expanduser("~/.claude/projects")
        if not os.path.exists(projects_dir):
            logger.error(f"Claude projects directory not found: {projects_dir}")
            sys.exit(1)
        
        importer = StreamingImporter()
        importer.import_all_projects(projects_dir)

if __name__ == "__main__":
    main()