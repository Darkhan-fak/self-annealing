import os
import math
import re
from pathlib import Path

def normalize_token(word: str) -> str:
    """
    Lowercases the word, strips common punctuation from boundaries,
    and stems suffixes like -ment, -ing, -ed, -es, -s.
    """
    w = word.lower().strip(".,!?\"'()[]{}*:;-")
    if not w:
        return ""
        
    changed = True
    while changed:
        changed = False
        for suffix in ["ment", "ing", "ed", "es", "s"]:
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                w = w[:-len(suffix)]
                changed = True
                break
    return w

def search_docs(project_dir: str, query: str) -> list[dict]:
    """
    Search for markdown files in project_dir recursively, ranking them
    using a BM25/TF-IDF style relevance scoring algorithm in pure Python.
    
    Args:
        project_dir (str): The project root directory to search.
        query (str): The search query.
        
    Returns:
        list[dict]: A list of dicts containing:
            - filename (str): Relative path to the markdown file from project_dir (forward-slash normalized).
            - file (str): Alias for filename.
            - score (float): BM25/TF-IDF relevance score.
            - match_score (float): Alias for score.
            - snippet (str): Snippet from the file around the first keyword match.
    """
    if not query:
        return []
        
    # Check if project_dir exists
    if not os.path.exists(project_dir):
        return []
        
    # Extract query tokens: split, strip punctuation, and stem
    query_words = query.split()
    query_tokens = []
    for qw in query_words:
        norm = normalize_token(qw)
        if norm:
            query_tokens.append(norm)
            
    if not query_tokens:
        return []
        
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
    
    # We will gather all documents and index them
    documents_data = []
    
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
                
                # Tokenize and count term frequencies
                tf = {}
                doc_len = 0
                words = content.split()
                for w in words:
                    norm = normalize_token(w)
                    if norm:
                        tf[norm] = tf.get(norm, 0) + 1
                        doc_len += 1
                        # Support substring match when words are not space-separated (e.g. AAAAtargetBBBB)
                        for q in query_tokens:
                            if q != norm and q in norm:
                                tf[q] = tf.get(q, 0) + 1
                        
                rel_path = os.path.relpath(file_path, project_path).replace('\\', '/')
                
                documents_data.append({
                    "file_path": file_path,
                    "rel_path": rel_path,
                    "content": content,
                    "tf": tf,
                    "doc_len": doc_len
                })
                
    if not documents_data:
        return []
        
    N = len(documents_data)
    
    # Compute document frequencies
    df = {}
    for doc in documents_data:
        for token in doc['tf']:
            df[token] = df.get(token, 0) + 1
            
    # Compute average document length
    total_tokens = sum(doc['doc_len'] for doc in documents_data)
    avgdl = total_tokens / N if N > 0 else 1.0
    if avgdl == 0:
        avgdl = 1.0
        
    # Pre-calculate IDF for query tokens
    idf_dict = {}
    for q in set(query_tokens):
        n_q = df.get(q, 0)
        # BM25 IDF formula with positive guard
        idf = math.log(1.0 + (N - n_q + 0.5) / (n_q + 0.5))
        if idf < 0:
            idf = 0.0
        idf_dict[q] = idf
        
    results = []
    k1 = 1.5
    b = 0.75
    
    for doc in documents_data:
        score = 0.0
        tf_dict = doc['tf']
        doc_len = doc['doc_len']
        
        for q in query_tokens:
            if q in tf_dict:
                f = tf_dict[q]
                denom = f + k1 * (1.0 - b + b * (doc_len / avgdl))
                score += idf_dict[q] * f * (k1 + 1.0) / denom
                
        if score > 0.0:
            # Generate snippet based on the earliest matching token
            earliest_idx = -1
            matched_len = 0
            
            content = doc['content']
            content_lower = content.lower()
            for q in query_tokens:
                idx = content_lower.find(q)
                if idx != -1:
                    if earliest_idx == -1 or idx < earliest_idx:
                        earliest_idx = idx
                        matched_len = len(q)
                    
            if earliest_idx != -1:
                start = max(0, earliest_idx - 60)
                end = min(len(content), earliest_idx + matched_len + 60)
                snippet_text = content[start:end]
                prefix = "..." if start > 0 else ""
                suffix = "..." if end < len(content) else ""
                snippet = f"{prefix}{snippet_text}{suffix}"
            else:
                snippet = ""
                
            results.append({
                "filename": doc['rel_path'],
                "file": doc['rel_path'],
                "score": score,
                "match_score": score,
                "snippet": snippet
            })
            
    # Rank by score descending, then by filename alphabetically
    results.sort(key=lambda x: (-x['score'], x['filename']))
    return results
