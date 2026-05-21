import argparse
import sys
import shutil
from pathlib import Path
from colorama import init, Fore, Style

from self_annealing.memory import (
    find_file_in_parents,
    search as memory_search,
    log_error,
    get_stats,
    list_all
)
from self_annealing.health import run_all_checks

def handle_init():
    cwd = Path.cwd()
    templates_dir = Path(__file__).parent / 'templates'
    
    claude_src = templates_dir / 'CLAUDE.md'
    error_src = templates_dir / 'error_log.md'
    
    claude_dest = cwd / 'CLAUDE.md'
    error_dest = cwd / 'error_log.md'
    
    copied = []
    
    if not claude_dest.exists():
        shutil.copy(claude_src, claude_dest)
        copied.append("CLAUDE.md")
    else:
        print(Fore.YELLOW + f"CLAUDE.md already exists at {claude_dest}" + Style.RESET_ALL)
        
    if not error_dest.exists():
        shutil.copy(error_src, error_dest)
        copied.append("error_log.md")
    else:
        print(Fore.YELLOW + f"error_log.md already exists at {error_dest}" + Style.RESET_ALL)
        
    if copied:
        print(Fore.GREEN + f"Initialized: {', '.join(copied)} created in the current directory." + Style.RESET_ALL)
    else:
        print(Fore.BLUE + "No template files were copied as they already exist." + Style.RESET_ALL)

def handle_search(args):
    error_log_path = find_file_in_parents('error_log.md')
    if not error_log_path:
        print(Fore.RED + "Error: error_log.md not found in parent directories. Please run 'anneal init' to initialize error tracking." + Style.RESET_ALL)
        sys.exit(1)
        
    results = memory_search(error_log_path, args.query, args.context)
    if not results:
        print(Fore.YELLOW + f"No matching entries found for search query: '{args.query}'" + Style.RESET_ALL)
        return
        
    for entry, relevance in results:
        # Determine color for relevance
        if relevance == 'HIGH':
            rel_color = Fore.RED + Style.BRIGHT
        elif relevance == 'MEDIUM':
            rel_color = Fore.YELLOW
        else:
            rel_color = Fore.CYAN
            
        print(f"{Fore.GREEN}{entry['id']}{Style.RESET_ALL} | {rel_color}{relevance}{Style.RESET_ALL} | {Fore.WHITE}{Style.BRIGHT}{entry['symptom']}{Style.RESET_ALL}")
        if entry['cause']:
            try:
                print(f"  {Fore.YELLOW}→ Cause:{Style.RESET_ALL} {entry['cause']}")
            except UnicodeEncodeError:
                print(f"  {Fore.YELLOW}-> Cause:{Style.RESET_ALL} {entry['cause']}")
        if entry['fix']:
            try:
                print(f"  {Fore.GREEN}→ Fix:{Style.RESET_ALL} {entry['fix']}")
            except UnicodeEncodeError:
                print(f"  {Fore.GREEN}-> Fix:{Style.RESET_ALL} {entry['fix']}")
        print()

def handle_health():
    # Use the directory where error_log.md or CLAUDE.md is found, or default to current directory
    project_root = find_file_in_parents('error_log.md')
    if not project_root:
        project_root = find_file_in_parents('CLAUDE.md')
    if not project_root:
        project_root = Path.cwd()
    else:
        project_root = project_root.parent
        
    print(f"Running health checks in project root: {Fore.BLUE}{project_root}{Style.RESET_ALL}\n")
    
    checks = run_all_checks(project_root)
    passed_count = 0
    
    # Order of checks
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
            try:
                print(f"{Fore.GREEN}[✓] {check_id}: {check_names[check_id]}{Style.RESET_ALL}")
            except UnicodeEncodeError:
                print(f"{Fore.GREEN}[PASSED] {check_id}: {check_names[check_id]}{Style.RESET_ALL}")
        else:
            try:
                print(f"{Fore.RED}[✗] {check_id}: {check_names[check_id]}{Style.RESET_ALL}")
            except UnicodeEncodeError:
                print(f"{Fore.RED}[FAILED] {check_id}: {check_names[check_id]}{Style.RESET_ALL}")
            # print error details indented
            indented = "\n".join("    " + line for line in message.splitlines())
            print(f"{Fore.RED}{indented}{Style.RESET_ALL}")
            
    print(f"\n{passed_count}/5 checks passed")
    if passed_count < 5:
        sys.exit(1)

def handle_log(args):
    error_log_path = find_file_in_parents('error_log.md')
    if not error_log_path:
        error_log_path = Path.cwd() / 'error_log.md'
        
    log_error(
        error_log_path,
        args.id,
        args.symptom,
        args.cause,
        args.fix,
        args.context,
        args.tokens
    )
    print(Fore.GREEN + f"Successfully logged error {args.id} to {error_log_path}" + Style.RESET_ALL)

def handle_stats():
    error_log_path = find_file_in_parents('error_log.md')
    if not error_log_path:
        print(Fore.RED + "Error: error_log.md not found." + Style.RESET_ALL)
        sys.exit(1)
        
    stats = get_stats(error_log_path)
    print(f"{Fore.GREEN}{stats['count']}{Style.RESET_ALL} entries | {Fore.GREEN}{stats['total_tokens']:,}{Style.RESET_ALL} tokens saved | Last modified: {Fore.BLUE}{stats['last_modified_str']}{Style.RESET_ALL}")

def handle_list():
    error_log_path = find_file_in_parents('error_log.md')
    if not error_log_path:
        print(Fore.RED + "Error: error_log.md not found." + Style.RESET_ALL)
        sys.exit(1)
        
    entries = list_all(error_log_path)
    if not entries:
        print(Fore.YELLOW + "No non-template error log entries found." + Style.RESET_ALL)
        return
        
    for entry in entries:
        print(f"{Fore.GREEN}{entry['id']}{Style.RESET_ALL} | {Fore.CYAN}{entry['context']:<10}{Style.RESET_ALL} | {Fore.WHITE}{entry['symptom']}{Style.RESET_ALL}")

def main():
    init(autoreset=True)
    
    parser = argparse.ArgumentParser(
        description="self-annealing: Persistent error memory & health checker for AI-assisted development"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")
    
    # Init subcommand
    subparsers.add_parser("init", help="Initialize CLAUDE.md and error_log.md templates in current directory")
    
    # Search subcommand
    search_parser = subparsers.add_parser("search", help="Search the error log memory")
    search_parser.add_argument("query", help="The error symptom or phrase to search for")
    search_parser.add_argument("--context", help="Filter by error context (e.g. database, deploy)")
    
    # Health subcommand
    subparsers.add_parser("health", help="Run project health checks")
    
    # Log subcommand
    log_parser = subparsers.add_parser("log", help="Log a new error resolution")
    log_parser.add_argument("--id", required=True, help="Error ID (e.g. E006)")
    log_parser.add_argument("--symptom", required=True, help="Symptom / error message")
    log_parser.add_argument("--cause", required=True, help="Root cause of the error")
    log_parser.add_argument("--fix", required=True, help="Steps to fix the error")
    log_parser.add_argument("--context", required=True, help="Categorization context")
    log_parser.add_argument("--tokens", type=int, default=0, help="Estimated tokens saved by avoiding this error")
    
    # Stats subcommand
    subparsers.add_parser("stats", help="Show error resolution memory statistics")
    
    # List subcommand
    subparsers.add_parser("list", help="List all recorded errors (excluding templates)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    if args.command == "init":
        handle_init()
    elif args.command == "search":
        handle_search(args)
    elif args.command == "health":
        handle_health()
    elif args.command == "log":
        handle_log(args)
    elif args.command == "stats":
        handle_stats()
    elif args.command == "list":
        handle_list()

if __name__ == "__main__":
    main()
