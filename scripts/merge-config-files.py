#!/usr/bin/env python3
"""Merge config-isolated/imported-files.json into config/imported-files.json"""

import json
import os
from pathlib import Path

def merge_configs():
    """Merge the two config files, preserving all unique entries."""
    base_path = Path(__file__).parent.parent
    
    main_config_path = base_path / "config/imported-files.json"
    isolated_config_path = base_path / "config-isolated/imported-files.json"
    
    # Read both config files
    with open(main_config_path, 'r') as f:
        main_config = json.load(f)
    
    with open(isolated_config_path, 'r') as f:
        isolated_config = json.load(f)
    
    # Merge projects
    merged_projects = main_config.get('projects', {})
    isolated_projects = isolated_config.get('projects', {})
    
    for project, files in isolated_projects.items():
        if project in merged_projects:
            # Merge file lists, avoiding duplicates
            existing_files = set(merged_projects[project])
            for file in files:
                if file not in existing_files:
                    merged_projects[project].append(file)
                    existing_files.add(file)
        else:
            # Add new project
            merged_projects[project] = files
    
    # Save merged config
    merged_config = {'projects': merged_projects}
    
    # Backup original
    backup_path = main_config_path.with_suffix('.json.backup')
    with open(backup_path, 'w') as f:
        json.dump(main_config, f, indent=2)
    
    # Write merged config
    with open(main_config_path, 'w') as f:
        json.dump(merged_config, f, indent=2)
    
    print(f"✅ Merged config files successfully")
    print(f"   - Backup saved to: {backup_path}")
    print(f"   - Projects in main config: {len(main_config.get('projects', {}))}")
    print(f"   - Projects in isolated config: {len(isolated_projects)}")
    print(f"   - Projects in merged config: {len(merged_projects)}")
    
    # Remove the isolated config directory
    isolated_config_path.unlink()
    isolated_config_path.parent.rmdir()
    print(f"   - Removed config-isolated directory")

if __name__ == "__main__":
    merge_configs()