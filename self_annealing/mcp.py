import os
import sys
import shutil
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Add parent directory of self_annealing package to sys.path to ensure correct imports
parent_dir = str(Path(__file__).parent.parent.resolve())
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from self_annealing import memory, health

# Create the FastMCP server instance
mcp = FastMCP("self-annealing")

@mcp.tool()
def anneal_init() -> str:
    """
    Initializes self-annealing in the current working directory.
    Copies CLAUDE.md and error_log.md templates into the current folder.
    """
    cwd = Path.cwd()
    templates_dir = Path(__file__).parent / 'templates'
    
    claude_src = templates_dir / 'CLAUDE.md'
    error_src = templates_dir / 'error_log.md'
    
    claude_dest = cwd / 'CLAUDE.md'
    error_dest = cwd / 'error_log.md'
    
    copied = []
    
    if not claude_dest.exists() and claude_src.exists():
        shutil.copy(claude_src, claude_dest)
        copied.append("CLAUDE.md")
        
    if not error_dest.exists() and error_src.exists():
        shutil.copy(error_src, error_dest)
        copied.append("error_log.md")
        
    if copied:
        return f"Success: Initialized self-annealing. Created {', '.join(copied)} in {cwd}."
    else:
        return f"Notice: self-annealing already initialized in {cwd} (files exist)."

@mcp.tool()
def anneal_search(query_symptom: str, query_context: str = None) -> str:
    """
    Searches the error log memory for relevant matches by symptom and/or context.
    Ranks results by relevance: HIGH, MEDIUM, LOW.
    """
    error_log_path = memory.find_file_in_parents('error_log.md')
    if not error_log_path:
        return "Error: error_log.md not found in parent directories. Please run 'anneal_init' first."
        
    results = memory.search(error_log_path, query_symptom, query_context)
    if not results:
        return f"No matching error records found for query: '{query_symptom}'."
        
    output = []
    for entry, relevance in results:
        output.append(f"[{relevance}] E{entry['id']} | Context: {entry['context']} | Symptom: {entry['symptom']}")
        if entry['cause']:
            output.append(f"  -> Cause: {entry['cause']}")
        if entry['fix']:
            output.append(f"  -> Fix: {entry['fix']}")
        if entry['tokens']:
            output.append(f"  -> Estimated Tokens Saved: {entry['tokens']}")
        output.append("")
        
    return "\n".join(output)

@mcp.tool()
def anneal_health() -> str:
    """
    Runs project health checks (HC001 to HC005) for the current workspace.
    Detects hardcoded ports, non-gitignored .env files, missing dependencies, and hardcoded secrets.
    """
    project_root = memory.find_file_in_parents('error_log.md')
    if not project_root:
        project_root = memory.find_file_in_parents('CLAUDE.md')
    if not project_root:
        project_root = Path.cwd()
    else:
        project_root = project_root.parent
        
    checks = health.run_all_checks(project_root)
    passed_count = 0
    results = [f"Running health checks in project root: {project_root}\n"]
    
    check_names = {
        'HC001': 'PORT binding check',
        'HC002': '.env in .gitignore check',
        'HC003': '.env file existence and example check',
        'HC004': 'requirements.txt / pyproject.toml check',
        'HC005': 'Secret scanner check'
    }
    
    for check_id in sorted(checks.keys()):
        passed, message = checks[check_id]
        if passed:
            passed_count += 1
            results.append(f"[✓] {check_id}: {check_names[check_id]}")
        else:
            results.append(f"[✗] {check_id}: {check_names[check_id]}")
            indented = "\n".join("    " + line for line in message.splitlines())
            results.append(indented)
            
    results.append(f"\n{passed_count}/5 checks passed")
    return "\n".join(results)

@mcp.tool()
def anneal_log(entry_id: str, symptom: str, cause: str, fix: str, context: str, tokens: int = 0) -> str:
    """
    Logs a new resolved error entry to the persistent error_log.md file.
    """
    error_log_path = memory.find_file_in_parents('error_log.md')
    if not error_log_path:
        error_log_path = Path.cwd() / 'error_log.md'
        
    memory.log_error(error_log_path, entry_id, symptom, cause, fix, context, tokens)
    return f"Success: Logged error entry {entry_id} into {error_log_path}."

@mcp.tool()
def anneal_stats() -> str:
    """
    Retrieves error resolution statistics: count of errors, saved tokens, and last modified time.
    """
    error_log_path = memory.find_file_in_parents('error_log.md')
    if not error_log_path:
        return "Error: error_log.md not found. Run 'anneal_init' to initialize error tracking."
        
    stats = memory.get_stats(error_log_path)
    return (
        f"{stats['count']} entries | "
        f"{stats['total_tokens']:,} tokens saved | "
        f"Last modified: {stats['last_modified_str']}"
    )

@mcp.tool()
def anneal_list() -> str:
    """
    Lists all logged error entries (excluding templates).
    """
    error_log_path = memory.find_file_in_parents('error_log.md')
    if not error_log_path:
        return "Error: error_log.md not found. Run 'anneal_init' to initialize error tracking."
        
    entries = memory.list_all(error_log_path)
    if not entries:
        return "No non-template error log entries found."
        
    output = []
    for entry in entries:
        output.append(f"E{entry['id']} | {entry['context'].ljust(10)} | {entry['symptom']}")
        
    return "\n".join(output)

if __name__ == "__main__":
    mcp.run()
