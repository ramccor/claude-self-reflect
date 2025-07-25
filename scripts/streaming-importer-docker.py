#!/usr/bin/env python3
"""
Memory-efficient streaming importer for Claude conversations.
Docker version that uses /logs as the projects directory.
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

# Docker-specific: Use /logs as the projects directory
PROJECTS_DIR = os.getenv("PROJECTS_DIR", "/logs")

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
        current_memory = self.get_memory_usage()
        memory_increase = current_memory - self.initial_memory
        
        if memory_increase > self.max_memory_mb:
            logger.warning(f"Memory limit exceeded: {memory_increase:.1f}MB > {self.max_memory_mb}MB")
            return False
        return True
    
    def log_memory_status(self):
        """Log current memory usage."""
        current_memory = self.get_memory_usage()
        memory_increase = current_memory - self.initial_memory
        logger.info(f"Memory usage: {current_memory:.1f}MB (increase: {memory_increase:.1f}MB)")

class StreamingImporter:
    def __init__(self):
        """Initialize the streaming importer."""
        self.memory_monitor = MemoryMonitor(MAX_MEMORY_MB)
        self.qdrant_client = QdrantClient(url=QDRANT_URL)
        self.model = None  # Lazy load to save memory
        self.state = self._load_state()
        self.checkpoints = {}  # For resuming within files
        self.total_imported = 0
        self.total_errors = 0
        
    def _load_state(self) -> Dict[str, Any]:
        """Load or initialize state."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        
        return {
            "projects": {},
            "last_updated": None,
            "total_imported": 0,
            "checkpoints": {}  # File-level checkpoints
        }
    
    def _save_state(self):
        """Save current state to disk."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            self.state["last_updated"] = datetime.now().isoformat()
            self.state["total_imported"] = self.total_imported
            self.state["checkpoints"] = self.checkpoints
            
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    @contextmanager
    def _get_model(self):
        """Context manager for model usage with memory cleanup."""
        try:
            if self.model is None:
                logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
                self.model = SentenceTransformer(EMBEDDING_MODEL)
            yield self.model
        finally:
            # Force garbage collection after batch processing
            gc.collect()
    
    def _get_collection_name(self, project_name: str) -> str:
        """Generate collection name for project."""
        project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
        return f"conv_{project_hash}"
    
    def _ensure_collection(self, collection_name: str):
        """Ensure collection exists with correct configuration."""
        collections = [col.name for col in self.qdrant_client.get_collections().collections]
        
        if collection_name not in collections:
            logger.info(f"Creating collection: {collection_name}")
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=384,  # all-MiniLM-L6-v2 embedding size
                    distance=Distance.COSINE
                )
            )
        else:
            # Verify collection configuration
            info = self.qdrant_client.get_collection(collection_name)
            if info.config.params.vectors.size != 384:
                logger.warning(f"Collection {collection_name} has wrong dimension: {info.config.params.vectors.size}")
    
    def _stream_jsonl(self, file_path: str, start_line: int = 0) -> Generator[Dict[str, Any], None, None]:
        """Stream JSONL file line by line starting from a specific line."""
        current_line = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                if line_num < start_line:
                    continue
                    
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Only process messages with content
                    if (data.get('message') and 
                        data['message'].get('role') and 
                        data['message'].get('content')):
                        
                        # Add line number for checkpointing
                        data['_line_number'] = line_num
                        yield data
                        
                except json.JSONDecodeError:
                    logger.debug(f"Skipping invalid JSON at line {line_num}")
                except Exception as e:
                    logger.error(f"Error processing line {line_num}: {e}")
    
    def _process_batch(self, batch: List[Dict[str, Any]], collection_name: str, project_name: str, file_path: str):
        """Process a batch of messages."""
        if not batch:
            return
            
        try:
            # Extract texts
            texts = []
            points = []
            
            for i, item in enumerate(batch):
                message = item['message']
                text = f"{message['role']}: {message['content'][:1000]}"  # Limit text length
                texts.append(text)
            
            # Generate embeddings with model context manager
            with self._get_model() as model:
                embeddings = model.encode(texts, batch_size=BATCH_SIZE)
            
            # Create points
            for i, (item, embedding) in enumerate(zip(batch, embeddings)):
                message = item['message']
                
                # Generate unique ID
                content_hash = hashlib.md5(
                    f"{project_name}_{file_path}_{item['_line_number']}_{message['content'][:100]}".encode()
                ).hexdigest()
                
                point = PointStruct(
                    id=content_hash,
                    vector=embedding.tolist(),
                    payload={
                        "role": message['role'],
                        "content": message['content'][:2000],  # Limit content size
                        "project": project_name,
                        "file": os.path.basename(file_path),
                        "line": item['_line_number'],
                        "timestamp": datetime.now().isoformat()
                    }
                )
                points.append(point)
            
            # Upload to Qdrant
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            self.total_imported += len(points)
            
            # Update checkpoint with last processed line
            if batch:
                last_line = batch[-1]['_line_number']
                self.checkpoints[file_path] = last_line
            
            logger.debug(f"Imported {len(points)} chunks from {os.path.basename(file_path)}")
            
        except Exception as e:
            logger.error(f"Failed to process batch: {e}")
            self.total_errors += 1
            raise
    
    def import_file(self, file_path: str, project_name: str, collection_name: str) -> int:
        """Import a single JSONL file with streaming and checkpointing."""
        logger.info(f"Importing {os.path.basename(file_path)} for project {project_name}")
        
        # Get checkpoint
        start_line = self.checkpoints.get(file_path, 0)
        if start_line > 0:
            logger.info(f"Resuming from line {start_line}")
        
        batch = []
        chunks_processed = 0
        file_total = 0
        
        try:
            for item in self._stream_jsonl(file_path, start_line):
                batch.append(item)
                
                # Process batch when full
                if len(batch) >= CHUNK_SIZE:
                    self._process_batch(batch, collection_name, project_name, file_path)
                    file_total += len(batch)
                    chunks_processed += 1
                    batch = []
                    
                    # Check memory periodically
                    if chunks_processed % 10 == 0:
                        if not self.memory_monitor.check_memory():
                            logger.warning("Memory limit reached, forcing garbage collection")
                            gc.collect()
                            
                            # If still over limit, save progress and exit
                            if not self.memory_monitor.check_memory():
                                self._save_state()
                                raise MemoryError("Memory limit exceeded")
                    
                    # Save checkpoint periodically
                    if chunks_processed % CHECKPOINT_INTERVAL == 0:
                        self._save_state()
                        logger.info(f"Checkpoint saved at {file_total} messages")
            
            # Process remaining batch
            if batch:
                self._process_batch(batch, collection_name, project_name, file_path)
                file_total += len(batch)
            
            # Mark file as complete
            self.checkpoints.pop(file_path, None)
            
            # Convert to relative path for state storage
            rel_path = file_path.replace(PROJECTS_DIR, "/logs")
            
            if project_name not in self.state["projects"]:
                self.state["projects"][project_name] = []
            if rel_path not in self.state["projects"][project_name]:
                self.state["projects"][project_name].append(rel_path)
            
            logger.info(f"✅ Imported {file_total} messages from {os.path.basename(file_path)}")
            return file_total
            
        except Exception as e:
            logger.error(f"Failed to import {file_path}: {e}")
            # Save checkpoint on error
            self._save_state()
            raise
    
    def import_project(self, project_path: str) -> int:
        """Import all JSONL files in a project directory."""
        project_name = os.path.basename(project_path)
        collection_name = self._get_collection_name(project_name)
        
        logger.info(f"📁 Importing project: {project_name}")
        
        # Ensure collection exists
        self._ensure_collection(collection_name)
        
        # Get list of JSONL files
        jsonl_files = []
        for file in os.listdir(project_path):
            if file.endswith('.jsonl'):
                file_path = os.path.join(project_path, file)
                rel_path = file_path.replace(PROJECTS_DIR, "/logs")
                
                # Skip already imported files
                if (project_name in self.state["projects"] and 
                    rel_path in self.state["projects"][project_name] and
                    file_path not in self.checkpoints):  # Unless there's a checkpoint
                    logger.debug(f"Skipping already imported: {file}")
                    continue
                    
                jsonl_files.append(file_path)
        
        if not jsonl_files:
            logger.info(f"No new files to import for {project_name}")
            return 0
        
        project_total = 0
        for file_path in sorted(jsonl_files):
            try:
                count = self.import_file(file_path, project_name, collection_name)
                project_total += count
                
                # Memory check between files
                self.memory_monitor.log_memory_status()
                gc.collect()
                
            except MemoryError:
                logger.error("Memory limit exceeded, stopping import")
                break
            except Exception as e:
                logger.error(f"Failed to import {file_path}: {e}")
                continue
        
        # Save state after each project
        self._save_state()
        
        return project_total
    
    def import_all(self):
        """Import all Claude projects."""
        projects_dir = PROJECTS_DIR
        
        if not os.path.exists(projects_dir):
            logger.error(f"Claude projects directory not found: {projects_dir}")
            return
        
        # Get list of projects
        projects = [
            d for d in os.listdir(projects_dir) 
            if os.path.isdir(os.path.join(projects_dir, d))
        ]
        
        logger.info(f"Found {len(projects)} projects to import")
        
        # Import each project
        for project_name in sorted(projects):
            project_path = os.path.join(projects_dir, project_name)
            
            try:
                count = self.import_project(project_path)
                
                # Log overall progress
                imported_projects = len(self.state["projects"])
                logger.info(
                    f"Progress: {imported_projects}/{len(projects)} projects "
                    f"({imported_projects/len(projects)*100:.1f}%), "
                    f"Total messages: {self.total_imported}"
                )
                
            except Exception as e:
                logger.error(f"Failed to import project {project_name}: {e}")
                continue
        
        # Final summary
        logger.info("=" * 60)
        logger.info(f"Import completed!")
        logger.info(f"Projects imported: {len(self.state['projects'])}/{len(projects)}")
        logger.info(f"Total messages: {self.total_imported}")
        logger.info(f"Total errors: {self.total_errors}")
        
        # Show collection summary
        logger.info("\nCollection summary:")
        for col in self.qdrant_client.get_collections().collections:
            if col.name.startswith("conv_"):
                info = self.qdrant_client.get_collection(col.name)
                logger.info(f"  {col.name}: {info.points_count} points")

def main():
    """Main entry point."""
    importer = StreamingImporter()
    
    if len(sys.argv) > 1:
        # Import specific project
        project_path = sys.argv[1]
        if os.path.exists(project_path):
            importer.import_project(project_path)
        else:
            logger.error(f"Project path not found: {project_path}")
    else:
        # Import all projects
        importer.import_all()

if __name__ == "__main__":
    main()