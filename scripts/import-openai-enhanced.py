#!/usr/bin/env python3
"""
Import Claude conversation logs from JSONL files into Qdrant vector database using Voyage AI embeddings.
Enhanced version with detailed progress tracking, time estimates, and dry-run mode.
"""

import json
import os
import glob
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import requests
import backoff
from tqdm import tqdm
import humanize
import sys
import argparse

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
LOGS_DIR = os.getenv("LOGS_DIR", "/logs")
STATE_FILE = os.getenv("STATE_FILE", "/config/imported-files.json")
VOYAGE_API_KEY = os.getenv("VOYAGE_KEY-2") or os.getenv("VOYAGE_KEY")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))  # Voyage supports batch embedding
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "10"))  # Can use larger chunks with 32k token limit
RATE_LIMIT_DELAY = 1  # 1 second between requests for paid account (60 RPM)
EMBEDDING_MODEL = "voyage-3.5-lite"
EMBEDDING_DIMENSIONS = 1024  # Voyage default dimensions
VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"

# Set up logging (less verbose for progress mode)
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

class EnhancedVoyageImporter:
    def __init__(self, dry_run=False, validate_only=False, preview=False):
        """Initialize the importer with Qdrant and Voyage AI.
        
        Args:
            dry_run: Simulate import without making changes
            validate_only: Only validate setup and files
            preview: Show sample chunks in dry-run mode
        """
        self.dry_run = dry_run
        self.validate_only = validate_only
        self.preview = preview
        
        if self.dry_run or self.validate_only:
            print(f"🔍 Running in {'VALIDATE-ONLY' if self.validate_only else 'DRY-RUN'} mode...")
            print("=" * 60)
        
        # Validate API key
        if not VOYAGE_API_KEY:
            if self.dry_run or self.validate_only:
                print("⚠️  VOYAGE_KEY environment variable not set")
                self.voyage_available = False
            else:
                raise ValueError("VOYAGE_KEY environment variable not set")
        else:
            self.voyage_available = True
            
        print("🚀 Initializing Claude-Self-Reflect Importer...")
        print("=" * 60)
        
        # Initialize clients (skip in validate-only mode)
        if not self.validate_only:
            try:
                self.qdrant_client = QdrantClient(url=QDRANT_URL, timeout=60)
                if not self.dry_run:
                    # Test connection
                    self.qdrant_client.get_collections()
            except Exception as e:
                if self.dry_run:
                    print(f"⚠️  Qdrant connection test failed: {e}")
                    self.qdrant_client = None
                else:
                    raise
        
        if self.voyage_available:
            self.voyage_headers = {
                "Authorization": f"Bearer {VOYAGE_API_KEY}",
                "Content-Type": "application/json"
            }
        
        self.state = self._load_state()
        self.total_imported = 0
        self.total_errors = 0
        self.start_time = time.time()
        
        # Statistics for progress tracking
        self.stats = {
            'files_processed': 0,
            'total_files': 0,
            'chunks_created': 0,
            'embeddings_generated': 0,
            'messages_processed': 0,
            'bytes_processed': 0,
            'api_calls': 0,
            'estimated_cost': 0.0,
            'sample_chunks': []
        }
        
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
                print(f"⚠️ Failed to load state: {e}")
        
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
        if self.dry_run:
            # In dry-run mode, just log what would happen
            print(f"[DRY-RUN] Would ensure collection: {collection_name}")
            return
            
        collections = [col.name for col in self.qdrant_client.get_collections().collections]
        
        if collection_name not in collections:
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
                raise ValueError(f"Dimension mismatch in collection {collection_name}")
    
    def _count_total_work(self) -> Tuple[int, int, int]:
        """Count total files and estimate chunks to process."""
        total_files = 0
        new_files = 0
        estimated_chunks = 0
        total_size = 0
        
        projects_dir = LOGS_DIR
        if not os.path.exists(projects_dir):
            return 0, 0, 0
        
        # Count all JSONL files
        for project_name in os.listdir(projects_dir):
            project_path = os.path.join(projects_dir, project_name)
            if os.path.isdir(project_path) and not project_name.startswith('.'):
                for file in os.listdir(project_path):
                    if file.endswith('.jsonl'):
                        total_files += 1
                        file_path = os.path.join(project_path, file)
                        
                        # Check if already imported
                        if not (project_name in self.state["projects"] and 
                               file_path in self.state["projects"][project_name]):
                            new_files += 1
                            
                            # Estimate chunks based on file size
                            try:
                                file_size = os.path.getsize(file_path)
                                total_size += file_size
                                # Rough estimate: 1 chunk per 10KB
                                estimated_chunks += max(1, file_size // 10240)
                            except:
                                estimated_chunks += 5  # Default estimate
        
        return total_files, new_files, estimated_chunks
    
    def _estimate_cost(self, text_count: int) -> float:
        """Estimate API cost for embeddings.
        
        Voyage AI pricing (as of 2024):
        - voyage-3.5-lite: $0.02 per 1M tokens
        - Estimated 500 tokens per chunk average
        """
        estimated_tokens = text_count * 500  # Average tokens per chunk
        cost_per_million = 0.02  # $0.02 per 1M tokens for voyage-3.5-lite
        return (estimated_tokens / 1_000_000) * cost_per_million
    
    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=5,
        on_backoff=lambda details: None  # Silent backoff
    )
    def _generate_embeddings(self, texts: List[str], progress_bar=None) -> List[List[float]]:
        """Generate embeddings using Voyage AI API with retry logic."""
        if self.dry_run:
            # In dry-run mode, simulate embeddings
            if progress_bar:
                progress_bar.set_description("[DRY-RUN] Simulating embeddings...")
            
            # Update cost estimation
            self.stats['estimated_cost'] += self._estimate_cost(len(texts))
            self.stats['api_calls'] += 1
            self.stats['embeddings_generated'] += len(texts)
            
            # Return fake embeddings
            return [[0.0] * EMBEDDING_DIMENSIONS for _ in texts]
            
        try:
            if progress_bar:
                progress_bar.set_description("🤖 Generating embeddings...")
            
            response = requests.post(
                VOYAGE_API_URL,
                headers=self.voyage_headers,
                json={
                    "input": texts,
                    "model": EMBEDDING_MODEL,
                    "input_type": "document"
                }
            )
            
            self.stats['api_calls'] += 1
            
            if response.status_code != 200:
                raise Exception(f"Voyage API error: {response.status_code} - {response.text}")
            
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            self.stats['embeddings_generated'] += len(embeddings)
            
            return embeddings
        except Exception as e:
            if progress_bar:
                progress_bar.set_description(f"❌ Embedding error: {str(e)[:30]}...")
            raise
    
    def _process_jsonl_file(self, file_path: str, progress_bar=None) -> List[Dict[str, Any]]:
        """Extract messages from a JSONL file with progress tracking."""
        messages = []
        file_size = os.path.getsize(file_path)
        self.stats['bytes_processed'] += file_size
        
        if progress_bar:
            progress_bar.set_description(f"📄 Reading {os.path.basename(file_path)[:30]}...")
        
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
                                self.stats['messages_processed'] += 1
                    except json.JSONDecodeError:
                        pass  # Skip invalid JSON
                    except Exception as e:
                        logger.debug(f"Error processing line {line_num}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
        
        return messages
    
    def _create_conversation_chunks(self, messages: List[Dict[str, Any]], progress_bar=None) -> List[Dict[str, Any]]:
        """Group messages into conversation chunks for better context."""
        chunks = []
        
        if progress_bar:
            progress_bar.set_description("✂️ Creating conversation chunks...")
        
        for i in range(0, len(messages), CHUNK_SIZE):
            chunk_messages = messages[i:i + CHUNK_SIZE]
            
            # Create conversation text - Voyage supports 32k tokens
            conversation_parts = []
            total_chars = 0
            max_chars = 100000  # Much larger limit with Voyage!
            
            for msg in chunk_messages:
                role = msg['role'].upper()
                content = msg['content']
                
                # Only truncate extremely long messages
                if len(content) > 20000:
                    content = content[:15000] + "\n\n[... truncated ...]\n\n" + content[-5000:]
                
                part = f"{role}: {content}"
                
                # Check if adding this would exceed limit
                if total_chars + len(part) > max_chars:
                    remaining = max_chars - total_chars
                    if remaining > 1000:
                        part = f"{role}: {content[:remaining-100]}..."
                        conversation_parts.append(part)
                    break
                
                conversation_parts.append(part)
                total_chars += len(part) + 2
            
            conversation_text = "\n\n".join(conversation_parts)
            
            # Extract metadata
            project_name = os.path.basename(os.path.dirname(chunk_messages[0]['file_path']))
            conversation_id = os.path.basename(chunk_messages[0]['file_path']).replace('.jsonl', '')
            
            # Generate unique ID
            chunk_id = hashlib.md5(
                f"{project_name}_{conversation_id}_{i}".encode()
            ).hexdigest()
            
            chunk_data = {
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
            }
            
            chunks.append(chunk_data)
            
            # Store sample chunks for preview
            if self.preview and len(self.stats['sample_chunks']) < 3:
                self.stats['sample_chunks'].append({
                    'project': project_name,
                    'file': os.path.basename(chunk_messages[0]['file_path']),
                    'preview': conversation_text[:500] + '...' if len(conversation_text) > 500 else conversation_text,
                    'message_count': len(chunk_messages)
                })
            
        self.stats['chunks_created'] += len(chunks)
        return chunks
    
    def _import_chunks_to_qdrant(self, chunks: List[Dict[str, Any]], collection_name: str, file_progress: tqdm):
        """Import conversation chunks to Qdrant with batched OpenAI embeddings."""
        if not chunks:
            return
        
        if self.dry_run:
            # In dry-run mode, simulate the import
            print(f"\n[DRY-RUN] Would import {len(chunks)} chunks to collection: {collection_name}")
            
            # Simulate progress
            for i in range(0, len(chunks), BATCH_SIZE):
                batch_size = min(BATCH_SIZE, len(chunks) - i)
                self.stats['api_calls'] += 1
                self.stats['embeddings_generated'] += batch_size
                self.total_imported += batch_size
                
                # Estimate cost
                self.stats['estimated_cost'] += self._estimate_cost(batch_size)
            
            return
        
        # Create sub-progress bar for chunks
        chunk_progress = tqdm(
            total=len(chunks),
            desc="📦 Uploading chunks",
            unit="chunk",
            leave=False,
            position=2
        )
        
        # Process in batches
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            texts = [chunk['text'] for chunk in batch]
            
            try:
                # Generate embeddings
                chunk_progress.set_description("🤖 Generating embeddings...")
                embeddings = self._generate_embeddings(texts, chunk_progress)
                
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
                chunk_progress.set_description("⬆️ Uploading to Qdrant...")
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                
                self.total_imported += len(points)
                chunk_progress.update(len(points))
                
                # Update speed in main progress
                elapsed = time.time() - self.start_time
                speed = self.total_imported / elapsed if elapsed > 0 else 0
                file_progress.set_postfix({
                    'chunks/s': f"{speed:.1f}",
                    'total': self.total_imported
                })
                
                # Add delay to respect rate limit
                if i + BATCH_SIZE < len(chunks):
                    chunk_progress.set_description(f"⏳ Rate limit delay ({RATE_LIMIT_DELAY}s)...")
                    time.sleep(RATE_LIMIT_DELAY)
                
            except Exception as e:
                chunk_progress.set_description(f"❌ Error: {str(e)[:30]}...")
                self.total_errors += 1
                # Continue with next batch instead of failing completely
        
        chunk_progress.close()
    
    def import_project(self, project_path: str, project_progress: tqdm = None) -> int:
        """Import all JSONL files in a project directory."""
        project_name = os.path.basename(project_path)
        collection_name = self._get_collection_name(project_name)
        
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
                    continue
                    
                jsonl_files.append(file_path)
        
        if not jsonl_files:
            return 0
        
        # Create file progress bar
        file_progress = tqdm(
            total=len(jsonl_files),
            desc=f"📁 {project_name}",
            unit="file",
            leave=False,
            position=1
        )
        
        project_total = 0
        for file_path in sorted(jsonl_files):
            file_name = os.path.basename(file_path)
            file_progress.set_description(f"📁 {project_name}/{file_name[:20]}...")
            
            # Extract messages
            messages = self._process_jsonl_file(file_path, file_progress)
            if not messages:
                file_progress.update(1)
                continue
            
            # Create chunks
            chunks = self._create_conversation_chunks(messages, file_progress)
            
            # Import to Qdrant
            self._import_chunks_to_qdrant(chunks, collection_name, file_progress)
            
            # Mark file as imported (only in non-dry-run mode)
            if not self.dry_run:
                if project_name not in self.state["projects"]:
                    self.state["projects"][project_name] = []
                self.state["projects"][project_name].append(file_path)
                
                # Save state after each file
                self._save_state()
            
            project_total += len(chunks)
            self.stats['files_processed'] += 1
            
            file_progress.update(1)
        
        file_progress.close()
        return project_total
    
    def validate_setup(self):
        """Validate the entire setup before import."""
        print("🔍 Validating setup...")
        print("=" * 60)
        
        validations = {
            "API Key": False,
            "Qdrant Connection": False,
            "Claude Logs": False,
            "File Format": False,
            "Disk Space": False
        }
        
        # Check API key
        if self.voyage_available:
            try:
                # Test with a single embedding
                response = requests.post(
                    VOYAGE_API_URL,
                    headers=self.voyage_headers,
                    json={
                        "input": ["test"],
                        "model": EMBEDDING_MODEL,
                        "input_type": "document"
                    }
                )
                if response.status_code == 200:
                    validations["API Key"] = True
                    print("✅ Voyage API key is valid")
                else:
                    print(f"❌ Voyage API key test failed: {response.status_code}")
            except Exception as e:
                print(f"❌ Voyage API connection failed: {e}")
        else:
            print("⚠️  No API key configured")
        
        # Check Qdrant
        if hasattr(self, 'qdrant_client') and self.qdrant_client:
            try:
                collections = self.qdrant_client.get_collections()
                validations["Qdrant Connection"] = True
                print(f"✅ Qdrant is accessible ({len(collections.collections)} collections)")
            except Exception as e:
                print(f"❌ Qdrant connection failed: {e}")
        else:
            print("⚠️  Qdrant client not initialized")
        
        # Check Claude logs
        projects_dir = LOGS_DIR
        if os.path.exists(projects_dir):
            total_files, _, _ = self._count_total_work()
            if total_files > 0:
                validations["Claude Logs"] = True
                print(f"✅ Found {total_files} conversation files")
            else:
                print("⚠️  No conversation files found")
        else:
            print(f"❌ Claude logs directory not found: {projects_dir}")
        
        # Validate file format
        if validations["Claude Logs"]:
            sample_validated = False
            for project in os.listdir(projects_dir):
                project_path = os.path.join(projects_dir, project)
                if os.path.isdir(project_path):
                    for file in os.listdir(project_path):
                        if file.endswith('.jsonl'):
                            file_path = os.path.join(project_path, file)
                            try:
                                messages = self._process_jsonl_file(file_path)
                                if messages:
                                    validations["File Format"] = True
                                    sample_validated = True
                                    print(f"✅ JSONL format validated ({len(messages)} messages in sample)")
                                    break
                            except Exception as e:
                                print(f"⚠️  Sample file validation failed: {e}")
                                break
                if sample_validated:
                    break
        
        # Check disk space
        try:
            import shutil
            stat = shutil.disk_usage("/")
            free_gb = stat.free / (1024 ** 3)
            if free_gb > 1:
                validations["Disk Space"] = True
                print(f"✅ Sufficient disk space ({free_gb:.1f} GB free)")
            else:
                print(f"⚠️  Low disk space ({free_gb:.1f} GB free)")
        except Exception:
            print("⚠️  Could not check disk space")
        
        # Summary
        print("\n" + "=" * 60)
        all_valid = all(validations.values())
        if all_valid:
            print("✅ All validations passed!")
        else:
            print("⚠️  Some validations failed or have warnings")
            print("\nFailed checks:")
            for check, passed in validations.items():
                if not passed:
                    print(f"  • {check}")
        
        return all_valid
    
    def import_all(self):
        """Import all Claude projects with enhanced progress tracking."""
        if self.validate_only:
            # Only run validation
            self.validate_setup()
            return
            
        projects_dir = LOGS_DIR
        
        if not os.path.exists(projects_dir):
            print(f"❌ Claude projects directory not found: {projects_dir}")
            return
        
        # Count total work
        print("🔍 Analyzing conversation history...")
        total_files, new_files, estimated_chunks = self._count_total_work()
        
        if new_files == 0:
            print("✅ All conversations already imported!")
            return
        
        # Calculate estimated cost
        estimated_cost = self._estimate_cost(estimated_chunks)
        
        print(f"\n📊 Import Summary:")
        print(f"  • Total files: {total_files}")
        print(f"  • New files to import: {new_files}")
        print(f"  • Estimated chunks: ~{estimated_chunks}")
        print(f"  • Estimated cost: ${estimated_cost:.4f}")
        print(f"  • Embedding model: {EMBEDDING_MODEL}")
        print(f"  • Batch size: {BATCH_SIZE}")
        
        if self.dry_run:
            print(f"\n🔍 DRY-RUN MODE - No changes will be made")
        
        print(f"\n⏳ Starting import...\n")
        
        # Get list of projects
        projects = [
            d for d in os.listdir(projects_dir) 
            if os.path.isdir(os.path.join(projects_dir, d)) and not d.startswith('.')
        ]
        
        # Main progress bar for projects
        project_progress = tqdm(
            total=len(projects),
            desc="🚀 Overall Progress",
            unit="project",
            position=0
        )
        
        # Import each project
        self.start_time = time.time()
        for project_name in sorted(projects):
            project_path = os.path.join(projects_dir, project_name)
            
            try:
                count = self.import_project(project_path, project_progress)
                
                # Update progress
                project_progress.update(1)
                
                # Calculate and display ETA
                elapsed = time.time() - self.start_time
                progress_pct = (project_progress.n / len(projects))
                if progress_pct > 0:
                    eta_seconds = (elapsed / progress_pct) - elapsed
                    eta_str = humanize.naturaldelta(eta_seconds)
                else:
                    eta_str = "calculating..."
                
                project_progress.set_postfix({
                    'ETA': eta_str,
                    'chunks': self.total_imported,
                    'errors': self.total_errors
                })
                
            except Exception as e:
                project_progress.set_description(f"❌ Error in {project_name}: {str(e)[:30]}...")
                self.total_errors += 1
                continue
        
        project_progress.close()
        
        # Final summary
        elapsed_time = time.time() - self.start_time
        print("\n" + "=" * 60)
        
        if self.dry_run:
            print("✅ Dry-Run Complete!")
        else:
            print("✅ Import Complete!")
            
        print("=" * 60)
        print(f"\n📊 Final Statistics:")
        print(f"  • Time elapsed: {humanize.naturaldelta(elapsed_time)}")
        
        if self.dry_run:
            print(f"  • Projects to import: {len(projects)}")
        else:
            print(f"  • Projects imported: {len(self.state['projects'])}/{len(projects)}")
            
        print(f"  • Files processed: {self.stats['files_processed']}")
        print(f"  • Messages processed: {self.stats['messages_processed']:,}")
        print(f"  • Chunks created: {self.stats['chunks_created']:,}")
        print(f"  • Embeddings {'would be' if self.dry_run else ''} generated: {self.stats['embeddings_generated']:,}")
        print(f"  • Total chunks {'would be' if self.dry_run else ''} imported: {self.total_imported:,}")
        print(f"  • API calls {'would be' if self.dry_run else ''} made: {self.stats['api_calls']:,}")
        print(f"  • Data processed: {humanize.naturalsize(self.stats['bytes_processed'])}")
        
        if elapsed_time > 0:
            print(f"  • Average speed: {self.total_imported/elapsed_time:.1f} chunks/second")
        
        if self.dry_run:
            print(f"  • 💰 Estimated cost: ${self.stats['estimated_cost']:.4f}")
        
        if self.total_errors > 0:
            print(f"  • ⚠️ Errors encountered: {self.total_errors}")
        
        # Show sample chunks in preview mode
        if self.preview and self.stats['sample_chunks']:
            print(f"\n📋 Sample Chunks Preview:")
            for i, sample in enumerate(self.stats['sample_chunks'], 1):
                print(f"\n--- Sample {i} ---")
                print(f"Project: {sample['project']}")
                print(f"File: {sample['file']}")
                print(f"Messages: {sample['message_count']}")
                print(f"Preview:\n{sample['preview']}")
        
        # Show collection summary (non-dry-run only)
        if not self.dry_run and hasattr(self, 'qdrant_client') and self.qdrant_client:
            print(f"\n📦 Collection Summary:")
            for col in self.qdrant_client.get_collections().collections:
                if col.name.endswith("_voyage"):
                    info = self.qdrant_client.get_collection(col.name)
                    print(f"  • {col.name}: {info.points_count:,} vectors")
        
        print(f"\n💡 Next steps:")
        if self.dry_run:
            print(f"  1. Review the statistics above")
            print(f"  2. Run without --dry-run to perform actual import")
            print(f"  3. Consider using --preview to see sample chunks")
        else:
            print(f"  1. Restart Claude Desktop to load the MCP server")
            print(f"  2. Try searching: 'What did we discuss about X?'")
            print(f"  3. Enable continuous import: docker compose --profile watch up -d")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import Claude conversation logs to Qdrant vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in dry-run mode to see what would happen
  python %(prog)s --dry-run
  
  # Validate setup only
  python %(prog)s --validate-only
  
  # Dry-run with preview of sample chunks
  python %(prog)s --dry-run --preview
  
  # Import a specific project
  python %(prog)s /path/to/project
  
  # Import all projects (normal mode)
  python %(prog)s
        """
    )
    
    parser.add_argument('project_path', nargs='?', help='Path to specific project to import')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Simulate import without making changes')
    parser.add_argument('--validate-only', action='store_true',
                        help='Only validate setup without importing')
    parser.add_argument('--preview', action='store_true',
                        help='Show sample chunks in dry-run mode')
    
    args = parser.parse_args()
    
    try:
        importer = EnhancedVoyageImporter(
            dry_run=args.dry_run,
            validate_only=args.validate_only,
            preview=args.preview
        )
        
        if args.project_path:
            # Import specific project
            if os.path.exists(args.project_path):
                print(f"📁 Importing single project: {os.path.basename(args.project_path)}")
                importer.import_project(args.project_path)
            else:
                print(f"❌ Project path not found: {args.project_path}")
        else:
            # Import all projects
            importer.import_all()
    except KeyboardInterrupt:
        print("\n\n⚠️ Import interrupted by user")
        if not args.dry_run and not args.validate_only:
            print("Progress has been saved. Run again to continue where you left off.")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()