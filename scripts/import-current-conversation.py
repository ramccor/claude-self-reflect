#!/usr/bin/env python3
"""Quick import of current conversation using Voyage AI"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import importlib.util
spec = importlib.util.spec_from_file_location("voyage_importer", 
    os.path.join(os.path.dirname(__file__), "import-conversations-voyage.py"))
voyage_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voyage_module)
VoyageConversationImporter = voyage_module.VoyageConversationImporter

def main():
    # Import just the current conversation
    importer = VoyageConversationImporter()
    
    project_path = "/Users/ramakrishnanannaswamy/.claude/projects/-Users-ramakrishnanannaswamy-memento-stack"
    target_file = "a2ae66a2-41f5-4b07-ab8b-353b5174af34.jsonl"
    
    print(f"Importing current conversation: {target_file}")
    
    # Process just this file
    file_path = os.path.join(project_path, target_file)
    if os.path.exists(file_path):
        chunks = importer.process_jsonl_file(file_path)
        if chunks:
            collection_name = importer.get_collection_name(os.path.basename(project_path))
            importer.import_chunks(chunks, collection_name)
            print(f"✅ Imported {len(chunks)} chunks from current conversation")
        else:
            print("❌ No chunks found in current conversation")
    else:
        print(f"❌ File not found: {file_path}")

if __name__ == "__main__":
    main()