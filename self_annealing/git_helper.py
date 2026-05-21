import os
import subprocess
from pathlib import Path
from self_annealing.memory import parse_error_log

def find_error_log(project_dir: str) -> str:
    """
    Finds the error_log.md file in the project.
    """
    found_paths = []
    for root, dirs, files in os.walk(project_dir):
        # Exclude common non-project directories to avoid searching unnecessarily
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in (
            'venv', 'venv2', '.venv', 'build', 'dist', 
            'self_annealing.egg-info', 'node_modules', 'tests', '__pycache__', '.pytest_cache'
        )]
        if "error_log.md" in files:
            found_paths.append(os.path.join(root, "error_log.md"))
            
    if not found_paths:
        return None
        
    # Prefer path that doesn't have "templates" in it, if possible
    non_templates = [p for p in found_paths if "templates" not in Path(p).parts]
    if non_templates:
        return non_templates[0]
    return found_paths[0]

def get_git_status(project_dir: str) -> list:
    """
    Runs git status --porcelain and returns a list of modified/staged files.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        lines = result.stdout.splitlines()
        files = []
        for line in lines:
            if len(line) > 3:
                # Format: XY path
                filepath = line[3:].strip().strip('"')
                files.append(filepath)
        return files
    except (subprocess.SubprocessError, FileNotFoundError):
        return []

def suggest_commit_message(project_dir: str) -> str:
    """
    Generates a structured commit message suggestion linking modified files
    to the symptom/fix of the recent error entry in error_log.md.
    """
    # 1. Get git status
    modified_files = get_git_status(project_dir)
    
    # 2. Find error_log.md
    error_log_path = find_error_log(project_dir)
    
    # 3. Parse entries
    entry = None
    if error_log_path:
        entries = parse_error_log(error_log_path)
        if entries:
            entry = entries[-1]
            
    if not entry:
        # Fallback if no error log or no entries
        commit_msg = "chore: update project files"
        if modified_files:
            commit_msg += "\n\nModified files:\n" + "\n".join(f"- {f}" for f in modified_files)
        return commit_msg
        
    symptom = entry.get("symptom", "").strip()
    cause = entry.get("cause", "").strip()
    fix = entry.get("fix", "").strip()
    context = entry.get("context", "").strip()
    
    # Determine scope from context
    scope = context if context else "core"
    
    # Create a concise summary/description from the fix
    summary = fix
    if summary:
        # Remove [TEMPLATE] prefix if present
        if summary.startswith("[TEMPLATE]"):
            summary = summary[len("[TEMPLATE]"):].strip()
        # Lowercase the first char of summary
        if len(summary) > 0:
            summary = summary[0].lower() + summary[1:]
        # Strip trailing period
        summary = summary.rstrip(".")
    else:
        summary = "fix error described in log"
        
    # Limit summary to a reasonable length for the commit title line (e.g. 50 chars)
    if len(summary) > 50:
        summary = summary[:47] + "..."
        
    commit_msg = f"fix({scope}): {summary}\n\n"
    
    if symptom:
        commit_msg += f"Symptom: {symptom}\n"
    if cause:
        commit_msg += f"Cause: {cause}\n"
    if fix:
        commit_msg += f"Fix: {fix}\n"
        
    if modified_files:
        commit_msg += "\nModified files:\n"
        for f in modified_files:
            commit_msg += f"- {f}\n"
            
    return commit_msg.strip()
