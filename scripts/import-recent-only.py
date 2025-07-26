#!/usr/bin/env python3
"""Import only recent conversation files from memento-stack project."""

import os
import sys
from datetime import datetime, timedelta

# Get the import script path
import_script = os.path.join(os.path.dirname(__file__), "import-openai.py")
project_path = os.path.expanduser("~/.claude/projects/-Users-ramakrishnanannaswamy-memento-stack")

# Get files modified in last 2 days
cutoff = datetime.now() - timedelta(days=2)
recent_files = []

for file in os.listdir(project_path):
    if file.endswith(".jsonl"):
        file_path = os.path.join(project_path, file)
        mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
        if mtime > cutoff:
            recent_files.append(file)

print(f"Found {len(recent_files)} recent files to import")

# Set environment variable
os.environ["VOYAGE_KEY"] = "pa-wdTYGObaxhs-XFKX2r7WCczRwEVNb9eYMTSO3yrQhZI"

# Import the whole project (the script will handle individual files)
os.system(f"python {import_script} {project_path}")