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
from self_annealing.safety import verify_command
from self_annealing.audit import audit_large_files
from self_annealing.dependencies import check_dependencies
from self_annealing.git_helper import suggest_commit_message
from self_annealing.pipeline import run_preflight_checks
from self_annealing.doc_search import search_docs

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

@mcp.tool()
def anneal_verify_cmd(command: str) -> str:
    """
    Verifies if a command is destructive and checks for unstaged changes.
    """
    passed, message = verify_command(command)
    if passed:
        return f"[✓] verified safe: {message}"
    else:
        return f"[✗] SAFETY WARNING: {message}"

@mcp.tool()
def anneal_audit() -> str:
    """
    Audits project for large files (>100KB) that are not matched in .gitignore.
    """
    large_files = audit_large_files(str(Path.cwd()))
    if not large_files:
        return "[✓] No non-gitignored large files (>100KB) found."
        
    output = [f"Found {len(large_files)} non-gitignored large files (>100KB):"]
    for lf in large_files:
        size_kb = lf['size'] / 1024
        output.append(f"  - {lf['path']} ({size_kb:.1f} KB)")
        output.append(f"    Warning: {lf['warning']}")
    return "\n".join(output)

@mcp.tool()
def anneal_check_deps() -> str:
    """
    Checks for dependency mismatches or missing packages declared in requirements.txt or pyproject.toml.
    """
    warnings = check_dependencies(str(Path.cwd()))
    if not warnings:
        return "[✓] All dependencies are satisfied."
    
    output = ["Dependency mismatches or missing packages found:"]
    for w in warnings:
        output.append(f"  ✗ {w}")
    return "\n".join(output)

@mcp.tool()
def anneal_commit_msg() -> str:
    """
    Suggests a Git commit message based on the recent error memory log entry.
    """
    return suggest_commit_message(str(Path.cwd()))

@mcp.tool()
def anneal_preflight() -> str:
    """
    Runs local CI/CD pre-flight checks (linting/formatting validation).
    """
    results = run_preflight_checks(str(Path.cwd()))
    if not results:
        return "No supported CI/CD tools (black, ruff, flake8, mypy, isort, pylint) detected/installed."
        
    output = []
    passed_all = True
    for tool, passed, msg in results:
        if passed:
            output.append(f"[✓] {tool}: Passed")
        else:
            passed_all = False
            output.append(f"[✗] {tool}: Failed")
            indented = "\n".join("    " + line for line in msg.splitlines())
            output.append(indented)
            
    if passed_all:
        output.insert(0, "[✓] All pre-flight checks passed successfully.")
    else:
        output.insert(0, "[✗] Some pre-flight checks failed.")
    return "\n".join(output)

@mcp.tool()
def anneal_search_docs(query: str) -> str:
    """
    Searches project Markdown documentation files for keyword matches.
    """
    results = search_docs(str(Path.cwd()), query)
    if not results:
        return "No documentation matches found."
        
    output = []
    for res in results:
        output.append(f"{res['file']} (score: {res['score']})")
        output.append(f"  Snippet: ...{res['snippet']}...")
        output.append("")
    return "\n".join(output)

if __name__ == "__main__":
    mcp.run()
