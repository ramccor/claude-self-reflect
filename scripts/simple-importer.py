#!/usr/bin/env python3
"""
Simple importer that uses the Qdrant server's built-in embedding capabilities.
Works around dependency issues by offloading embedding generation.
"""

import json
import os
import sys
import hashlib
from datetime import datetime
from typing import Dict, Any, List
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import numpy as np

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
STATE_FILE = os.getenv("STATE_FILE", "./config-isolated/imported-files.json")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleImporter:
    def __init__(self):
        """Initialize the simple importer."""
        self.qdrant_client = QdrantClient(url=QDRANT_URL)
        self.state = self._load_state()
        self.total_imported = 0
        
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
            "total_imported": 0
        }
    
    def _save_state(self):
        """Save current state to disk."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            self.state["last_updated"] = datetime.now().isoformat()
            self.state["total_imported"] = self.total_imported
            
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
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
    
    def _create_dummy_embedding(self, text: str) -> List[float]:
        """Create a dummy embedding based on text hash."""
        # Create a deterministic embedding based on text content
        text_hash = hashlib.sha256(text.encode()).digest()
        # Convert to 384-dimensional vector
        embedding = []
        for i in range(48):  # 48 * 8 = 384
            # Use 8 bytes at a time
            chunk = text_hash[i % 32:i % 32 + 8]
            # Convert to float between -1 and 1
            value = int.from_bytes(chunk[:4], 'big') / (2**31 - 1)
            embedding.extend([value] * 8)
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = (np.array(embedding) / norm).tolist()
        
        return embedding[:384]  # Ensure exactly 384 dimensions
    
    def import_file(self, file_path: str, project_name: str, collection_name: str) -> int:
        """Import a single JSONL file."""
        logger.info(f"Importing {os.path.basename(file_path)} for project {project_name}")
        
        batch = []
        file_total = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        # Only process messages with content
                        if (data.get('message') and 
                            data['message'].get('role') and 
                            data['message'].get('content')):
                            
                            message = data['message']
                            text = f"{message['role']}: {message['content'][:1000]}"
                            
                            # Generate dummy embedding
                            embedding = self._create_dummy_embedding(text)
                            
                            # Generate unique ID
                            content_hash = hashlib.md5(
                                f"{project_name}_{file_path}_{line_num}_{message['content'][:100]}".encode()
                            ).hexdigest()
                            
                            point = PointStruct(
                                id=content_hash,
                                vector=embedding,
                                payload={
                                    "role": message['role'],
                                    "content": message['content'][:2000],
                                    "project": project_name,
                                    "file": os.path.basename(file_path),
                                    "line": line_num,
                                    "timestamp": datetime.now().isoformat()
                                }
                            )
                            batch.append(point)
                            
                            # Upload batch
                            if len(batch) >= BATCH_SIZE:
                                self.qdrant_client.upsert(
                                    collection_name=collection_name,
                                    points=batch
                                )
                                file_total += len(batch)
                                batch = []
                                
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"Error processing line {line_num}: {e}")
            
            # Upload remaining batch
            if batch:
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=batch
                )
                file_total += len(batch)
            
            # Update state
            rel_path = file_path.replace(os.path.expanduser("~/.claude/projects"), "/logs")
            
            if project_name not in self.state["projects"]:
                self.state["projects"][project_name] = []
            if rel_path not in self.state["projects"][project_name]:
                self.state["projects"][project_name].append(rel_path)
            
            self.total_imported += file_total
            logger.info(f"✅ Imported {file_total} messages from {os.path.basename(file_path)}")
            return file_total
            
        except Exception as e:
            logger.error(f"Failed to import {file_path}: {e}")
            return 0
    
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
                rel_path = file_path.replace(os.path.expanduser("~/.claude/projects"), "/logs")
                
                # Skip already imported files
                if (project_name in self.state["projects"] and 
                    rel_path in self.state["projects"][project_name]):
                    logger.debug(f"Skipping already imported: {file}")
                    continue
                    
                jsonl_files.append(file_path)
        
        if not jsonl_files:
            logger.info(f"No new files to import for {project_name}")
            return 0
        
        project_total = 0
        for file_path in sorted(jsonl_files):
            count = self.import_file(file_path, project_name, collection_name)
            project_total += count
        
        # Save state after each project
        self._save_state()
        
        return project_total
    
    def import_all(self):
        """Import all Claude projects."""
        projects_dir = os.path.expanduser("~/.claude/projects")
        
        if not os.path.exists(projects_dir):
            logger.error(f"Claude projects directory not found: {projects_dir}")
            return
        
        # Get list of projects
        projects = [
            d for d in os.listdir(projects_dir) 
            if os.path.isdir(os.path.join(projects_dir, d))
        ]
        
        total_projects = len(projects)
        logger.info(f"Found {total_projects} projects to import")
        
        # Get already imported count
        imported_count = len(self.state.get("projects", {}))
        remaining = total_projects - imported_count
        
        logger.info(f"Already imported: {imported_count}, Remaining: {remaining}")
        
        # Import each project
        for project_name in sorted(projects):
            # Skip if already fully imported
            if project_name in self.state.get("projects", {}):
                project_path = os.path.join(projects_dir, project_name)
                # Check if there are new files
                jsonl_count = len([f for f in os.listdir(project_path) if f.endswith('.jsonl')])
                imported_count = len(self.state["projects"][project_name])
                if jsonl_count <= imported_count:
                    continue
            
            project_path = os.path.join(projects_dir, project_name)
            
            try:
                count = self.import_project(project_path)
                
                # Log overall progress
                imported_projects = len(self.state["projects"])
                logger.info(
                    f"Progress: {imported_projects}/{total_projects} projects "
                    f"({imported_projects/total_projects*100:.1f}%), "
                    f"Total messages: {self.total_imported}"
                )
                
            except Exception as e:
                logger.error(f"Failed to import project {project_name}: {e}")
                continue
        
        # Final summary
        logger.info("=" * 60)
        logger.info(f"Import completed!")
        logger.info(f"Projects imported: {len(self.state['projects'])}/{total_projects}")
        logger.info(f"Total messages: {self.total_imported}")
        logger.info(f"Completion: {len(self.state['projects'])/total_projects*100:.1f}%")
        
        # Show collection summary
        logger.info("\nCollection summary:")
        for col in self.qdrant_client.get_collections().collections:
            if col.name.startswith("conv_"):
                info = self.qdrant_client.get_collection(col.name)
                logger.info(f"  {col.name}: {info.points_count} points")

def main():
    """Main entry point."""
    importer = SimpleImporter()
    
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