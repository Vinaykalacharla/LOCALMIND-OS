import os
import time
import difflib
from pathlib import Path
from typing import List, Dict, Any

class VersioningService:
    def __init__(self, versions_dir: Path):
        self.versions_dir = Path(versions_dir)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        
    def save_version(self, source_file: str, text: str) -> None:
        """Saves a new version of the extracted text if it differs from the latest version."""
        safe_name = "".join([c if c.isalnum() or c in " .-_" else "_" for c in source_file])
        file_dir = self.versions_dir / safe_name
        file_dir.mkdir(parents=True, exist_ok=True)
        
        # Check latest version
        versions = self.get_versions(source_file)
        if versions:
            latest = versions[0]
            latest_path = file_dir / latest["version_id"]
            if latest_path.exists():
                with open(latest_path, "r", encoding="utf-8") as f:
                    latest_text = f.read()
                if latest_text == text:
                    return # No change
                    
        version_id = f"{int(time.time())}.txt"
        with open(file_dir / version_id, "w", encoding="utf-8") as f:
            f.write(text)

    def get_versions(self, source_file: str) -> List[Dict[str, Any]]:
        safe_name = "".join([c if c.isalnum() or c in " .-_" else "_" for c in source_file])
        file_dir = self.versions_dir / safe_name
        if not file_dir.exists():
            return []
            
        versions = []
        for p in file_dir.glob("*.txt"):
            try:
                timestamp = int(p.stem)
                versions.append({
                    "version_id": p.name,
                    "timestamp": timestamp,
                })
            except ValueError:
                pass
                
        versions.sort(key=lambda x: x["timestamp"], reverse=True)
        return versions

    def get_diff(self, source_file: str, v1_id: str, v2_id: str) -> str:
        safe_name = "".join([c if c.isalnum() or c in " .-_" else "_" for c in source_file])
        file_dir = self.versions_dir / safe_name
        
        p1 = file_dir / v1_id
        p2 = file_dir / v2_id
        
        if not p1.exists() or not p2.exists():
            return "Error: One or both versions not found."
            
        with open(p1, "r", encoding="utf-8") as f:
            t1 = f.readlines()
        with open(p2, "r", encoding="utf-8") as f:
            t2 = f.readlines()
            
        diff = difflib.unified_diff(t1, t2, fromfile=v1_id, tofile=v2_id, n=3)
        return "".join(diff)
