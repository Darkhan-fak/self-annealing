import os
from pathlib import Path

def search_docs(project_dir: str, query: str) -> list[dict]:
    """
    Search for markdown files in project_dir recursively, ranking them
    by the occurrences of keywords in the query (case-insensitive).
    
    Args:
        project_dir (str): The project root directory to search.
        query (str): The search query.
        
    Returns:
        list[dict]: A list of dicts containing:
            - filename (str): Relative path to the markdown file from project_dir (forward-slash normalized).
            - score (int): Total occurrences of the keywords.
            - match_score (int): Alias for score.
            - snippet (str): Snippet from the file around the first keyword match.
    """
    if not query:
        return []
        
    # Check if project_dir exists
    if not os.path.exists(project_dir):
        return []
        
    # Extract keywords: lowercase, split by whitespace, and strip common punctuation
    words = query.lower().split()
    keywords = []
    for w in words:
        kw = w.strip(".,!?\"'()[]{}*:;-")
        if kw:
            keywords.append(kw)
            
    if not keywords:
        return []
        
    results = []
    exclude_dirs = {
        '.git',
        'node_modules',
        '__pycache__',
        '.pytest_cache',
        '.venv',
        'venv',
        'env',
        'build',
        'dist'
    }
    
    project_path = Path(project_dir).resolve()
    
    for root, dirs, files in os.walk(project_path):
        # Exclude directories in-place to prevent os.walk from visiting them
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.') and not d.endswith('.egg-info')]
        
        for file in files:
            if file.lower().endswith('.md'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception:
                    continue
                    
                content_lower = content.lower()
                # Count total keyword occurrences
                score = sum(content_lower.count(kw) for kw in keywords)
                
                if score > 0:
                    # Find earliest occurrence of any keyword for snippet
                    earliest_idx = -1
                    matched_kw = ""
                    for kw in keywords:
                        idx = content_lower.find(kw)
                        if idx != -1:
                            if earliest_idx == -1 or idx < earliest_idx:
                                earliest_idx = idx
                                matched_kw = kw
                                
                    if earliest_idx != -1:
                        start = max(0, earliest_idx - 60)
                        end = min(len(content), earliest_idx + len(matched_kw) + 60)
                        snippet_text = content[start:end]
                        prefix = "..." if start > 0 else ""
                        suffix = "..." if end < len(content) else ""
                        snippet = f"{prefix}{snippet_text}{suffix}"
                    else:
                        snippet = ""
                        
                    # Get relative path with forward slashes for cross-platform stability
                    rel_path = os.path.relpath(file_path, project_path).replace('\\', '/')
                    
                    results.append({
                        "filename": rel_path,
                        "file": rel_path,
                        "score": score,
                        "match_score": score,
                        "snippet": snippet
                    })
                    
    # Rank by score descending, then by filename ascending for deterministic output
    results.sort(key=lambda x: (-x['score'], x['filename']))
    return results
