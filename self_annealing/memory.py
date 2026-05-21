import os
import re
import datetime
from pathlib import Path

def find_file_in_parents(filename, start_dir=None):
    """
    Walks up parent directories from start_dir to find filename.
    Returns the Path to the file if found, otherwise None.
    """
    if start_dir is None:
        start_dir = Path.cwd()
    curr = Path(start_dir).resolve()
    for parent in [curr] + list(curr.parents):
        target = parent / filename
        if target.exists():
            return target
    return None

def parse_error_log(file_path):
    """
    Parses error_log.md and returns a list of error entries.
    Each entry is a dict with keys: id, symptom, cause, fix, context, tokens.
    """
    if not file_path or not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return []
    
    parts = content.split('## Error ')
    entries = []
    
    for part in parts[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        
        # The first line of the part is the ID
        entry_id = lines[0].strip()
        
        symptom = ""
        cause = ""
        fix = ""
        context = ""
        tokens = 0
        
        for line in lines[1:]:
            line_str = line.strip()
            if not line_str:
                continue
            
            symptom_match = re.match(r'^-\s*\*\*Symptom\*\*:\s*(.*)', line_str, re.IGNORECASE)
            if symptom_match:
                symptom = symptom_match.group(1).strip()
                continue
                
            cause_match = re.match(r'^-\s*\*\*Cause\*\*:\s*(.*)', line_str, re.IGNORECASE)
            if cause_match:
                cause = cause_match.group(1).strip()
                continue
                
            fix_match = re.match(r'^-\s*\*\*Fix\*\*:\s*(.*)', line_str, re.IGNORECASE)
            if fix_match:
                fix = fix_match.group(1).strip()
                continue
                
            context_match = re.match(r'^-\s*\*\*Context\*\*:\s*(.*)', line_str, re.IGNORECASE)
            if context_match:
                context = context_match.group(1).strip()
                continue
                
            tokens_match = re.match(r'^-\s*\*\*Tokens\*\*:\s*(\d+)', line_str, re.IGNORECASE)
            if tokens_match:
                try:
                    tokens = int(tokens_match.group(1).strip())
                except ValueError:
                    tokens = 0
                continue
        
        entries.append({
            'id': entry_id,
            'symptom': symptom,
            'cause': cause,
            'fix': fix,
            'context': context,
            'tokens': tokens
        })
        
    return entries

def search(file_path, query_symptom, query_context=None):
    """
    Searches the error log and ranks matches by relevance:
    - HIGH: Exact match of symptom
    - MEDIUM: Partial match of symptom OR context match
    - LOW: Match of individual words in symptom
    Returns a list of tuples (entry, relevance).
    """
    entries = parse_error_log(file_path)
    results = []
    
    if not query_symptom:
        return []
    
    query_symptom_clean = query_symptom.strip().lower()
    query_words = [w.lower() for w in query_symptom.split() if w.strip()]
    
    for entry in entries:
        entry_symptom_clean = entry['symptom'].lower()
        entry_context_clean = entry['context'].lower()
        
        relevance = None
        
        # 1. HIGH: Exact match
        if query_symptom_clean == entry_symptom_clean:
            relevance = 'HIGH'
        # 2. MEDIUM: Partial match of symptom OR context match
        elif (query_symptom_clean in entry_symptom_clean) or (query_context and query_context.strip().lower() == entry_context_clean):
            relevance = 'MEDIUM'
        # 3. LOW: Match of individual words
        elif any(word in entry_symptom_clean for word in query_words):
            relevance = 'LOW'
            
        if relevance:
            results.append((entry, relevance))
            
    # Sort: HIGH (0) > MEDIUM (1) > LOW (2)
    relevance_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    results.sort(key=lambda x: relevance_order[x[1]])
    
    return results

def log_error(file_path, entry_id, symptom, cause, fix, context, tokens):
    """
    Appends a new error entry to the error log file.
    Creates the file if it does not exist.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Error Log\n\n")
            
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = ""
        
    # Ensure proper newlines before appending
    prefix = ""
    if content and not content.endswith('\n'):
        prefix = "\n\n"
    elif content and not content.endswith('\n\n'):
        prefix = "\n"
        
    new_entry = prefix + f"## Error {entry_id}\n"
    new_entry += f"- **Symptom**: {symptom}\n"
    new_entry += f"- **Cause**: {cause}\n"
    new_entry += f"- **Fix**: {fix}\n"
    new_entry += f"- **Context**: {context}\n"
    new_entry += f"- **Tokens**: {tokens}\n"
    
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(new_entry)

def get_stats(file_path):
    """
    Calculates error resolution statistics:
    - Number of entries
    - Sum of saved tokens
    - Time elapsed since last modification of error_log.md
    """
    if not file_path or not os.path.exists(file_path):
        return {
            'count': 0,
            'total_tokens': 0,
            'last_modified_str': "N/A"
        }
        
    entries = parse_error_log(file_path)
    count = len(entries)
    total_tokens = sum(entry['tokens'] for entry in entries)
    
    try:
        mtime = os.path.getmtime(file_path)
        dt = datetime.datetime.fromtimestamp(mtime)
        now = datetime.datetime.now()
        diff = now - dt
        
        if diff.days == 0:
            if diff.seconds < 60:
                last_modified_str = "just now"
            elif diff.seconds < 3600:
                minutes = diff.seconds // 60
                last_modified_str = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                hours = diff.seconds // 3600
                last_modified_str = f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            last_modified_str = f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    except Exception:
        last_modified_str = "unknown"
        
    return {
        'count': count,
        'total_tokens': total_tokens,
        'last_modified_str': last_modified_str
    }

def list_all(file_path):
    """
    Lists all non-template entries (filtering out entries containing '[TEMPLATE]')
    """
    entries = parse_error_log(file_path)
    return [e for e in entries if "[TEMPLATE]" not in e['symptom']]
