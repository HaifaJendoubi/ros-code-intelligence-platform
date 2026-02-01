# backend/app/file_tree.py
"""
File tree builder for project structure visualization
"""

from pathlib import Path
from typing import List
from .models import FileNode
from .config import settings


def is_relevant_file(path: Path) -> bool:
    """
    Check if file is relevant for display
    
    Args:
        path: File path to check
        
    Returns:
        bool: True if file should be included in tree
    """
    # Check if path contains ignored directories
    path_str = str(path).lower()
    for ignored in settings.IGNORED_PATHS:
        if ignored in path_str:
            return False
    
    # Check file extension
    if path.is_file():
        return path.suffix.lower() in settings.RELEVANT_EXTENSIONS
    
    return True


def build_file_tree(path: Path, base_path: Path = None) -> FileNode:
    """
    Recursively build file tree structure
    
    Args:
        path: Current path to process
        base_path: Base path for relative path calculation
        
    Returns:
        FileNode: File tree node
        
    Raises:
        ValueError: If path doesn't exist
    """
    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    
    if base_path is None:
        base_path = path.parent
    
    is_dir = path.is_dir()
    
    # Calculate relative path
    try:
        rel_path = path.relative_to(base_path)
    except ValueError:
        rel_path = path
    
    # Create node
    node = FileNode(
        name=path.name or "root",
        path=str(rel_path),
        type="folder" if is_dir else "file",
        size=path.stat().st_size if not is_dir else None,
        children=[] if is_dir else None
    )
    
    # Process children for directories
    if is_dir:
        try:
            children: List[FileNode] = []
            
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                # Skip hidden files and ignored paths
                if item.name.startswith('.'):
                    continue
                
                if not is_relevant_file(item):
                    continue
                
                # Recursively build child node
                try:
                    child = build_file_tree(item, base_path)
                    children.append(child)
                except Exception as e:
                    # Skip problematic files but continue processing
                    continue
            
            node.children = children if children else None
            
        except PermissionError:
            # Can't read directory, leave children as empty
            pass
    
    return node