#!/usr/bin/env python3
"""
Streaming import for large Claude conversation logs.
Processes files in chunks without loading entire file into memory.
"""

import json
import os
import sys
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Generator
import logging
import backoff
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
STATE_FILE = os.getenv("STATE_FILE", "./config-isolated/imported-files.json")
LOGS_DIR = os.getenv("LOGS_DIR", os.path.expanduser("~/.claude/projects"))
VOYAGE_API_KEY = os.getenv("VOYAGE_KEY_2") or os.getenv("VOYAGE_KEY")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "10"))
STREAMING_BUFFER_SIZE = 100  # Process every 100 messages
RATE_LIMIT_DELAY = 0.1
EMBEDDING_MODEL = "voyage-3-large"
EMBEDDING_DIMENSIONS = 1024
VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"

class StreamingVoyageImporter:
    def __init__(self):
        """Initialize the streaming importer."""
        if not VOYAGE_API_KEY:
            raise ValueError("VOYAGE_KEY environment variable not set")
            
        self.qdrant_client = QdrantClient(url=QDRANT_URL)
        self.state = self._load_state()
        self.total_imported = 0
        self.total_errors = 0
        
        logger.info(f"Connected to Qdrant at {QDRANT_URL}")
        
    def _load_state(self) -> Dict[str, Any]:
        """Load import state from file."""
        default_state = {
            "projects": {},
            "last_updated": None,
            "mode": "isolated",
            "total_imported": 0
        }
        
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        
        return default_state
    
    def _save_state(self):
        """Save import state to file."""
        self.state["last_updated"] = datetime.now().isoformat()
        self.state["total_imported"] = self.total_imported
        
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=5,
        on_backoff=lambda details: logger.warning(f"Backing off {details['wait']}s after {details['tries']} tries")
    )
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Voyage AI API with batching."""
        headers = {
            "Authorization": f"Bearer {VOYAGE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": texts,
            "model": EMBEDDING_MODEL,
            "input_type": "document"
        }
        
        try:
            response = requests.post(VOYAGE_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            
            # Add small delay to respect rate limits
            time.sleep(RATE_LIMIT_DELAY)
            
            return embeddings
            
        except requests.Timeout:
            logger.error("Voyage API request timed out after 30 seconds")
            raise
        except Exception as e:
            logger.error(f"Voyage API error: {e}")
            raise
    
    def stream_jsonl_messages(self, file_path: str, buffer_size: int = STREAMING_BUFFER_SIZE) -> Generator[List[Dict[str, Any]], None, None]:
        """Stream messages from JSONL file in buffers without loading entire file."""
        buffer = []
        line_count = 0
        total_lines = 0
        skipped_lines = 0
        
        # Extract expected session ID from filename
        expected_session_id = os.path.splitext(os.path.basename(file_path))[0]
        logger.info(f"Starting to stream file: {os.path.basename(file_path)} (expecting session: {expected_session_id})")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    total_lines = line_num
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        # Check session ID matches expected
                        session_id = data.get('sessionId', '')
                        if session_id != expected_session_id:
                            skipped_lines += 1
                            logger.debug(f"Skipping line {line_num}: different session ID ({session_id})")
                            continue
                        
                        # Extract message if present
                        if 'message' in data and data['message']:
                            msg = data['message']
                            if msg.get('role') and msg.get('content'):
                                content = msg['content']
                                # Handle content array (common in Claude messages)
                                if isinstance(content, list) and len(content) > 0:
                                    # Extract text from first content item
                                    content_item = content[0]
                                    if isinstance(content_item, dict):
                                        content = content_item.get('text', str(content_item))
                                elif isinstance(content, dict):
                                    content = content.get('text', json.dumps(content))
                                
                                buffer.append({
                                    'role': msg['role'],
                                    'content': content,
                                    'file_path': file_path,
                                    'line_number': line_num,
                                    'timestamp': data.get('timestamp', datetime.now().isoformat())
                                })
                                line_count += 1
                                
                                # Yield buffer when it reaches the specified size
                                if len(buffer) >= buffer_size:
                                    logger.info(f"Buffer full, yielding {len(buffer)} messages (total so far: {line_count})")
                                    yield buffer
                                    buffer = []
                                    
                    except json.JSONDecodeError:
                        logger.debug(f"Skipping invalid JSON at line {line_num}")
                        skipped_lines += 1
                    except Exception as e:
                        logger.error(f"Error processing line {line_num}: {e}")
                        skipped_lines += 1
                
                # Yield any remaining messages
                if buffer:
                    logger.info(f"Yielding final buffer with {len(buffer)} messages")
                    yield buffer
                
                logger.info(f"Completed streaming file: processed {total_lines} lines, {line_count} messages, {skipped_lines} skipped")
                    
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
    
    def process_message_buffer(self, messages: List[Dict[str, Any]], project_name: str, collection_name: str, conversation_id: str):
        """Process a buffer of messages into chunks and import them."""
        chunks = []
        
        # Create chunks from message buffer
        for i in range(0, len(messages), CHUNK_SIZE):
            chunk_messages = messages[i:i + CHUNK_SIZE]
            
            # Create conversation text
            conversation_text = "\n\n".join([
                f"{msg['role'].upper()}: {msg['content'][:500]}"
                for msg in chunk_messages
            ])
            
            # Add metadata
            timestamps = [msg['timestamp'] for msg in chunk_messages]
            first_timestamp = min(timestamps) if timestamps else datetime.now().isoformat()
            
            chunk_id = hashlib.md5(
                f"{conversation_id}_{first_timestamp}_{len(chunks)}".encode()
            ).hexdigest()
            
            chunks.append({
                'id': chunk_id,
                'text': conversation_text,
                'metadata': {
                    'project': project_name,
                    'conversation_id': conversation_id,
                    'timestamp': first_timestamp,
                    'chunk_index': len(chunks),
                    'message_count': len(chunk_messages),
                    'roles': list(set(msg['role'] for msg in chunk_messages))
                }
            })
        
        # Import chunks if we have any
        if chunks:
            self._import_chunks_to_qdrant(chunks, collection_name)
    
    def _import_chunks_to_qdrant(self, chunks: List[Dict[str, Any]], collection_name: str):
        """Import conversation chunks to Qdrant."""
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
                    # Include both text and metadata in payload
                    payload = chunk['metadata'].copy()
                    payload['text'] = chunk['text']
                    
                    points.append(PointStruct(
                        id=chunk['id'],
                        vector=embedding,
                        payload=payload
                    ))
                
                # Upsert to Qdrant
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True
                )
                
                self.total_imported += len(points)
                logger.info(f"Imported batch of {len(points)} chunks (total: {self.total_imported})")
                
            except Exception as e:
                logger.error(f"Failed to import batch: {e}")
                self.total_errors += 1
    
    def import_large_file(self, file_path: str, project_name: str):
        """Import a large JSONL file using streaming."""
        logger.info(f"🚀 Starting streaming import of {os.path.basename(file_path)}")
        
        # Get collection name
        project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
        collection_name = f"conv_{project_hash}_voyage"
        
        # Ensure collection exists
        collections = [c.name for c in self.qdrant_client.get_collections().collections]
        if collection_name not in collections:
            logger.info(f"Creating collection: {collection_name}")
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=EMBEDDING_DIMENSIONS, distance=Distance.COSINE)
            )
        
        # Extract conversation ID from filename
        conversation_id = os.path.splitext(os.path.basename(file_path))[0]
        
        # Stream and process the file
        chunk_count = 0
        message_count = 0
        
        try:
            logger.info(f"Starting to process chunks from generator")
            for message_buffer in self.stream_jsonl_messages(file_path):
                logger.info(f"Received buffer with {len(message_buffer)} messages")
                self.process_message_buffer(message_buffer, project_name, collection_name, conversation_id)
                chunk_count += 1
                message_count += len(message_buffer)
                logger.info(f"Processed chunk {chunk_count} with {len(message_buffer)} messages (total: {message_count})")
                
                # Save state periodically
                if chunk_count % 10 == 0:
                    self._save_state()
            
            # Log final statistics
            logger.info(f"Finished processing {chunk_count} chunks with {message_count} total messages")
            
            # Mark file as imported
            if project_name not in self.state["projects"]:
                self.state["projects"][project_name] = []
            if file_path not in self.state["projects"][project_name]:
                self.state["projects"][project_name].append(file_path)
            
            self._save_state()
            logger.info(f"✅ Completed streaming import of {os.path.basename(file_path)} - {chunk_count} chunks, {message_count} messages, {self.total_imported} vectors")
            
        except Exception as e:
            logger.error(f"Error during streaming import: {e}")
            raise

def main():
    """Main entry point for streaming import."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Streaming import for large conversation files")
    parser.add_argument("--project", help="Project directory path")
    parser.add_argument("--limit", type=int, help="Limit number of files to process")
    args = parser.parse_args()
    
    importer = StreamingVoyageImporter()
    
    # If project path is provided via command line
    if args.project and os.path.exists(args.project):
        project_name = os.path.basename(args.project)
        files_processed = 0
        
        # Find all JSONL files in the project
        for file_path in Path(args.project).glob("*.jsonl"):
            if args.limit and files_processed >= args.limit:
                break
                
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            logger.info(f"Processing {file_path.name} ({file_size_mb:.1f} MB)")
            importer.import_large_file(str(file_path), project_name)
            files_processed += 1
    else:
        # No specific project specified - scan for all projects
        base_path = os.getenv("LOGS_PATH", "/logs")
        if os.path.exists(base_path):
            # Scan for all project directories
            for project_dir in Path(base_path).iterdir():
                if project_dir.is_dir() and not project_dir.name.startswith('.'):
                    # Look for JSONL files in this project
                    jsonl_files = list(project_dir.glob("*.jsonl"))
                    if jsonl_files:
                        for jsonl_file in jsonl_files:
                            file_size_mb = jsonl_file.stat().st_size / (1024 * 1024)
                            logger.info(f"Processing {jsonl_file.name} ({file_size_mb:.1f} MB) from project {project_dir.name}")
                            importer.import_large_file(str(jsonl_file), project_dir.name)
    
    logger.info(f"Streaming import complete! Total chunks: {importer.total_imported}")

if __name__ == "__main__":
    main()