#!/usr/bin/env python3
"""
Continuous importer for Claude conversations.
Monitors for new/updated JSONL files and imports them to Qdrant using Voyage AI embeddings.
"""

import os
import sys
import time
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Set
import logging
from pathlib import Path

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
VOYAGE_API_KEY = os.getenv("VOYAGE_KEY")
VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
STATE_FILE = os.getenv("STATE_FILE", "./config/imported-files.json")
CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # 5 minutes
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "5"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ContinuousImporter:
    def __init__(self):
        """Initialize the continuous importer."""
        self.state = self.load_state()
        self.processed_files = set()
        
        # Load processed files from state
        for project, files in self.state.get("projects", {}).items():
            self.processed_files.update(files)
        
        logger.info(f"Loaded {len(self.processed_files)} already processed files")
        
    def load_state(self) -> Dict:
        """Load import state."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        return {"projects": {}}
    
    def save_state(self):
        """Save import state."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            self.state["last_updated"] = datetime.now().isoformat()
            
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            logger.debug("State saved successfully")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def find_new_files(self, days_back: int = 7) -> Dict[str, List[str]]:
        """Find new or updated JSONL files."""
        cutoff_time = datetime.now() - timedelta(days=days_back)
        new_files = {}
        
        for project_dir in os.listdir(CLAUDE_PROJECTS_DIR):
            project_path = os.path.join(CLAUDE_PROJECTS_DIR, project_dir)
            if not os.path.isdir(project_path):
                continue
            
            # Convert to logs path format
            logs_project_name = project_dir
            
            for file_name in os.listdir(project_path):
                if not file_name.endswith('.jsonl'):
                    continue
                
                file_path = os.path.join(project_path, file_name)
                logs_path = f"/logs/{logs_project_name}/{file_name}"
                
                # Check if file is new or updated
                try:
                    mtime = os.path.getmtime(file_path)
                    if datetime.fromtimestamp(mtime) >= cutoff_time:
                        if logs_path not in self.processed_files:
                            if logs_project_name not in new_files:
                                new_files[logs_project_name] = []
                            new_files[logs_project_name].append({
                                'real_path': file_path,
                                'logs_path': logs_path,
                                'mtime': mtime
                            })
                except Exception as e:
                    logger.error(f"Error checking file {file_path}: {e}")
        
        return new_files
    
    def import_new_files(self, new_files: Dict[str, List[Dict]]):
        """Import new files to Qdrant."""
        total_imported = 0
        
        for project_name, files in new_files.items():
            logger.info(f"Processing {len(files)} new files for project: {project_name}")
            
            # Import using the existing import script
            for file_info in files:
                try:
                    # Call the import-single-project.py script for this specific file
                    import subprocess
                    
                    # Get the actual project directory path
                    project_dir = os.path.join(CLAUDE_PROJECTS_DIR, project_name)
                    
                    # Run the import script
                    result = subprocess.run([
                        sys.executable,
                        "import-single-project.py",
                        project_dir
                    ], capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        # Mark file as processed
                        if project_name not in self.state["projects"]:
                            self.state["projects"][project_name] = []
                        
                        self.state["projects"][project_name].append(file_info['logs_path'])
                        self.processed_files.add(file_info['logs_path'])
                        self.save_state()
                        
                        total_imported += 1
                        logger.info(f"✅ Imported: {file_info['logs_path']}")
                    else:
                        logger.error(f"Failed to import {file_info['logs_path']}: {result.stderr}")
                        
                except Exception as e:
                    logger.error(f"Error importing {file_info['logs_path']}: {e}")
        
        return total_imported
    
    def run_once(self):
        """Run one import cycle."""
        logger.info("Checking for new files...")
        
        # Find new files from the last 7 days
        new_files = self.find_new_files(days_back=7)
        
        total_new = sum(len(files) for files in new_files.values())
        
        if total_new > 0:
            logger.info(f"Found {total_new} new files across {len(new_files)} projects")
            
            # Import new files
            imported = self.import_new_files(new_files)
            logger.info(f"Imported {imported} new files")
        else:
            logger.info("No new files found")
    
    def run_continuous(self):
        """Run continuous import loop."""
        logger.info(f"Starting continuous import (checking every {CHECK_INTERVAL} seconds)")
        
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in import cycle: {e}")
            
            # Wait before next check
            logger.info(f"Waiting {CHECK_INTERVAL} seconds before next check...")
            time.sleep(CHECK_INTERVAL)

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Continuous importer for Claude conversations")
    parser.add_argument("--once", action="store_true", help="Run once instead of continuously")
    args = parser.parse_args()
    
    if not VOYAGE_API_KEY:
        logger.error("VOYAGE_KEY environment variable not set")
        sys.exit(1)
    
    importer = ContinuousImporter()
    
    if args.once:
        importer.run_once()
    else:
        importer.run_continuous()

if __name__ == "__main__":
    main()