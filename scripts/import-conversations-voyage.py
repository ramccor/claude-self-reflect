#!/usr/bin/env python3
"""
Import Claude conversation logs from JSONL files into Qdrant vector database using Voyage AI embeddings.
Clean implementation with 32k token context window.
"""

import json
import os
import glob
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import requests
import backoff

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
LOGS_DIR = os.getenv("LOGS_DIR", "/logs")
STATE_FILE = os.getenv("STATE_FILE", "/config/imported-files.json")
VOYAGE_API_KEY = os.getenv("VOYAGE_KEY-2") or os.getenv("VOYAGE_KEY")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))  # Voyage supports batch embedding
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "10"))  # Can use larger chunks with 32k token limit
RATE_LIMIT_DELAY = 0.1  # 100ms between requests for faster imports
EMBEDDING_MODEL = "voyage-3.5-lite"
EMBEDDING_DIMENSIONS = 1024  # Voyage default dimensions
VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VoyageConversationImporter:
    def __init__(self):
        """Initialize the importer with Qdrant and Voyage AI."""
        if not VOYAGE_API_KEY:
            raise ValueError("VOYAGE_KEY environment variable not set")
            
        self.qdrant_client = QdrantClient(url=QDRANT_URL, timeout=60)
        self.voyage_headers = {
            "Authorization": f"Bearer {VOYAGE_API_KEY}",
            "Content-Type": "application/json"
        }
        self.state = self._load_state()
        self.total_imported = 0
        self.total_errors = 0
        
    def _load_state(self) -> Dict[str, Any]:
        """Load or initialize state."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    # Handle old format (files list) vs new format (projects dict)
                    if 'files' in data and 'projects' not in data:
                        # Convert old format to new format
                        projects = {}
                        for file_path in data.get('files', []):
                            # Extract project name from file path
                            parts = file_path.split('/')
                            if len(parts) >= 3:
                                project_name = parts[2]
                                if project_name not in projects:
                                    projects[project_name] = []
                                projects[project_name].append(file_path)
                        return {
                            "projects": projects,
                            "last_updated": data.get('lastUpdated'),
                            "total_imported": len(data.get('files', []))
                        }
                    # New format
                    return data
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
        """Generate collection name for project with Voyage suffix."""
        project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
        return f"conv_{project_hash}_voyage"
    
    def _ensure_collection(self, collection_name: str):
        """Ensure collection exists with correct configuration for OpenAI embeddings."""
        collections = [col.name for col in self.qdrant_client.get_collections().collections]
        
        if collection_name not in collections:
            logger.info(f"Creating collection: {collection_name} with {EMBEDDING_DIMENSIONS} dimensions")
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIMENSIONS,
                    distance=Distance.COSINE
                )
            )
        else:
            # Verify dimensions
            info = self.qdrant_client.get_collection(collection_name)
            if info.config.params.vectors.size != EMBEDDING_DIMENSIONS:
                logger.error(f"Collection {collection_name} has wrong dimensions: {info.config.params.vectors.size}")
                raise ValueError(f"Dimension mismatch in collection {collection_name}")
    
    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=5,
        on_backoff=lambda details: logger.warning(f"Backing off {details['wait']}s after {details['tries']} tries")
    )
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Voyage AI API with retry logic."""
        try:
            response = requests.post(
                VOYAGE_API_URL,
                headers=self.voyage_headers,
                json={
                    "input": texts,
                    "model": EMBEDDING_MODEL,
                    "input_type": "document"  # For document embeddings
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Voyage API error: {response.status_code} - {response.text}")
            
            data = response.json()
            return [item["embedding"] for item in data["data"]]
        except Exception as e:
            logger.error(f"Voyage API error: {e}")
            raise
    
    def _process_jsonl_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract messages from a JSONL file."""
        messages = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        # Extract message if present
                        if 'message' in data and data['message']:
                            msg = data['message']
                            if msg.get('role') and msg.get('content'):
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
                        logger.debug(f"Skipping invalid JSON at line {line_num}")
                    except Exception as e:
                        logger.error(f"Error processing line {line_num}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
        
        return messages
    
    def _create_conversation_chunks(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group messages into conversation chunks for better context."""
        chunks = []
        
        for i in range(0, len(messages), CHUNK_SIZE):
            chunk_messages = messages[i:i + CHUNK_SIZE]
            
            # Create conversation text - Voyage supports 32k tokens
            # Rough estimate: ~4 chars per token, so ~128k chars max
            # We'll use 100k chars to be safe
            conversation_parts = []
            total_chars = 0
            max_chars = 100000  # Much larger limit with Voyage!
            
            for msg in chunk_messages:
                role = msg['role'].upper()
                content = msg['content']
                
                # Only truncate extremely long messages
                if len(content) > 20000:
                    # Keep first 15000 and last 5000 chars
                    content = content[:15000] + "\n\n[... truncated ...]\n\n" + content[-5000:]
                
                part = f"{role}: {content}"
                
                # Check if adding this would exceed limit
                if total_chars + len(part) > max_chars:
                    # For the last message, try to fit what we can
                    remaining = max_chars - total_chars
                    if remaining > 1000:  # Only add if we can fit meaningful content
                        part = f"{role}: {content[:remaining-100]}..."
                        conversation_parts.append(part)
                    break
                
                conversation_parts.append(part)
                total_chars += len(part) + 2  # +2 for newlines
            
            conversation_text = "\n\n".join(conversation_parts)
            
            # Extract metadata
            project_name = os.path.basename(os.path.dirname(chunk_messages[0]['file_path']))
            conversation_id = os.path.basename(chunk_messages[0]['file_path']).replace('.jsonl', '')
            
            # Generate unique ID
            chunk_id = hashlib.md5(
                f"{project_name}_{conversation_id}_{i}".encode()
            ).hexdigest()
            
            chunks.append({
                'id': chunk_id,
                'text': conversation_text,
                'metadata': {
                    'project': project_name,
                    'conversation_id': conversation_id,
                    'chunk_index': i // CHUNK_SIZE,
                    'message_count': len(chunk_messages),
                    'start_role': chunk_messages[0]['role'],
                    'timestamp': chunk_messages[0]['timestamp'],
                    'file': os.path.basename(chunk_messages[0]['file_path'])
                }
            })
        
        return chunks
    
    def _import_chunks_to_qdrant(self, chunks: List[Dict[str, Any]], collection_name: str):
        """Import conversation chunks to Qdrant with batched OpenAI embeddings."""
        if not chunks:
            return
        
        # Process in batches
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            texts = [chunk['text'] for chunk in batch]
            
            try:
                # Generate embeddings
                embeddings = self._generate_embeddings(texts)
                
                # Create points
                points = []
                for chunk, embedding in zip(batch, embeddings):
                    point = PointStruct(
                        id=chunk['id'],
                        vector=embedding,
                        payload={
                            'text': chunk['text'][:2000],  # Limit text size
                            **chunk['metadata']
                        }
                    )
                    points.append(point)
                
                # Upload to Qdrant
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                
                self.total_imported += len(points)
                logger.info(f"Imported batch of {len(points)} chunks (total: {self.total_imported})")
                
                # Add delay to respect rate limit (3 RPM)
                if i + BATCH_SIZE < len(chunks) and i % 100 == 0:  # Only delay every 100 chunks
                    logger.info(f"Waiting {RATE_LIMIT_DELAY}s for rate limit...")
                    time.sleep(RATE_LIMIT_DELAY)
                
            except Exception as e:
                logger.error(f"Failed to import batch: {e}")
                self.total_errors += 1
                # Continue with next batch instead of failing completely
    
    def import_project(self, project_path: str) -> int:
        """Import all JSONL files in a project directory."""
        project_name = os.path.basename(project_path)
        collection_name = self._get_collection_name(project_name)
        
        logger.info(f"📁 Importing project: {project_name} to collection: {collection_name}")
        
        # Ensure collection exists
        self._ensure_collection(collection_name)
        
        # Get list of JSONL files
        jsonl_files = []
        for file in os.listdir(project_path):
            if file.endswith('.jsonl'):
                file_path = os.path.join(project_path, file)
                
                # Skip already imported files
                if (project_name in self.state["projects"] and 
                    file_path in self.state["projects"][project_name]):
                    logger.debug(f"Skipping already imported: {file}")
                    continue
                    
                jsonl_files.append(file_path)
        
        if not jsonl_files:
            logger.info(f"No new files to import for {project_name}")
            return 0
        
        project_total = 0
        for file_path in sorted(jsonl_files):
            logger.info(f"Processing: {os.path.basename(file_path)}")
            
            # Extract messages
            messages = self._process_jsonl_file(file_path)
            if not messages:
                logger.warning(f"No messages found in {file_path}")
                continue
            
            # Create chunks
            chunks = self._create_conversation_chunks(messages)
            
            # Import to Qdrant
            self._import_chunks_to_qdrant(chunks, collection_name)
            
            # Mark file as imported
            if project_name not in self.state["projects"]:
                self.state["projects"][project_name] = []
            self.state["projects"][project_name].append(file_path)
            
            project_total += len(chunks)
            
            # Save state after each file
            self._save_state()
        
        logger.info(f"✅ Imported {project_total} chunks from {len(jsonl_files)} files")
        return project_total
    
    def import_all(self):
        """Import all Claude projects."""
        projects_dir = LOGS_DIR
        
        if not os.path.exists(projects_dir):
            logger.error(f"Claude projects directory not found: {projects_dir}")
            return
        
        # Get list of projects
        projects = [
            d for d in os.listdir(projects_dir) 
            if os.path.isdir(os.path.join(projects_dir, d)) and not d.startswith('.')
        ]
        
        logger.info(f"Found {len(projects)} projects to import")
        
        # Import each project
        start_time = time.time()
        for idx, project_name in enumerate(sorted(projects), 1):
            project_path = os.path.join(projects_dir, project_name)
            
            try:
                logger.info(f"\n[{idx}/{len(projects)}] Processing: {project_name}")
                count = self.import_project(project_path)
                
                # Log progress
                imported_projects = len(self.state["projects"])
                progress = (imported_projects / len(projects)) * 100
                logger.info(
                    f"Progress: {imported_projects}/{len(projects)} projects "
                    f"({progress:.1f}%), Total chunks: {self.total_imported}"
                )
                
            except Exception as e:
                logger.error(f"Failed to import project {project_name}: {e}")
                self.total_errors += 1
                continue
        
        # Final summary
        elapsed_time = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"Import completed in {elapsed_time:.1f} seconds!")
        logger.info(f"Projects imported: {len(self.state['projects'])}/{len(projects)}")
        logger.info(f"Total chunks: {self.total_imported}")
        logger.info(f"Total errors: {self.total_errors}")
        
        # Show collection summary
        logger.info("\nCollection summary:")
        for col in self.qdrant_client.get_collections().collections:
            if col.name.endswith("_voyage"):
                info = self.qdrant_client.get_collection(col.name)
                logger.info(f"  {col.name}: {info.points_count} points")

def main():
    """Main entry point."""
    importer = VoyageConversationImporter()
    
    if len(os.sys.argv) > 1:
        # Import specific project
        project_path = os.sys.argv[1]
        if os.path.exists(project_path):
            importer.import_project(project_path)
        else:
            logger.error(f"Project path not found: {project_path}")
    else:
        # Import all projects
        importer.import_all()

if __name__ == "__main__":
    main()