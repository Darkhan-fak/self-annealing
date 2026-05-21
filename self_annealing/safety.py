import subprocess
import shlex
import os

def get_subcommands(cmd: str) -> list[str]:
    """
    Splits a command string into subcommands by shell operators (&&, ||, ;, |),
    respecting single/double quotes, and recursively extracts/inspects nested
    subshells ($(...) and `...`).
    """
    subcommands = []
    current_token = []
    
    i = 0
    n = len(cmd)
    
    in_single_quote = False
    in_double_quote = False
    escaped = False
    
    while i < n:
        char = cmd[i]
        
        if escaped:
            current_token.append(char)
            escaped = False
            i += 1
            continue
            
        if char == '\\':
            current_token.append(char)
            escaped = True
            i += 1
            continue
            
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current_token.append(char)
            i += 1
            continue
            
        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current_token.append(char)
            i += 1
            continue
            
        if not in_single_quote and not in_double_quote:
            # Check for nested subshell $(...)
            if cmd[i:i+2] == "$(":
                # Find matching close parenthesis
                paren_depth = 1
                j = i + 2
                sub_cmd_chars = []
                sub_escaped = False
                sub_single_quote = False
                sub_double_quote = False
                while j < n and paren_depth > 0:
                    sub_char = cmd[j]
                    if sub_escaped:
                        sub_cmd_chars.append(sub_char)
                        sub_escaped = False
                        j += 1
                        continue
                    if sub_char == '\\':
                        sub_cmd_chars.append(sub_char)
                        sub_escaped = True
                        j += 1
                        continue
                    if sub_char == "'" and not sub_double_quote:
                        sub_single_quote = not sub_single_quote
                    elif sub_char == '"' and not sub_single_quote:
                        sub_double_quote = not sub_double_quote
                    elif not sub_single_quote and not sub_double_quote:
                        if sub_char == '(':
                            paren_depth += 1
                        elif sub_char == ')':
                            paren_depth -= 1
                    
                    if paren_depth > 0:
                        sub_cmd_chars.append(sub_char)
                        j += 1
                
                sub_cmd = "".join(sub_cmd_chars)
                # Recursively extract subcommands from inside the subshell
                subcommands.extend(get_subcommands(sub_cmd))
                
                current_token.append(cmd[i:j+1])
                i = j + 1
                continue
                
            # Check for backtick subshell `...`
            elif char == '`':
                j = i + 1
                sub_cmd_chars = []
                sub_escaped = False
                while j < n:
                    sub_char = cmd[j]
                    if sub_escaped:
                        sub_cmd_chars.append(sub_char)
                        sub_escaped = False
                        j += 1
                        continue
                    if sub_char == '\\':
                        sub_cmd_chars.append(sub_char)
                        sub_escaped = True
                        j += 1
                        continue
                    if sub_char == '`':
                        break
                    sub_cmd_chars.append(sub_char)
                    j += 1
                
                sub_cmd = "".join(sub_cmd_chars)
                subcommands.extend(get_subcommands(sub_cmd))
                current_token.append(cmd[i:j+1])
                i = j + 1
                continue
                
            # Check for operators: &&, ||, ;, |
            if cmd[i:i+2] in ("&&", "||"):
                subcommands.append("".join(current_token).strip())
                current_token = []
                i += 2
                continue
            elif char in (';', '|'):
                subcommands.append("".join(current_token).strip())
                current_token = []
                i += 1
                continue
                
        current_token.append(char)
        i += 1
        
    if current_token:
        subcommands.append("".join(current_token).strip())
        
    return [s for s in subcommands if s]

def get_executable_base(exe: str) -> str:
    base = os.path.basename(exe)
    if base.endswith(".exe"):
        base = base[:-4]
    return base

def is_command_destructive(sub_cmd: str) -> bool:
    try:
        tokens = shlex.split(sub_cmd)
    except ValueError:
        tokens = sub_cmd.split()
        
    if not tokens:
        return False
        
    exe = get_executable_base(tokens[0])
    
    # 1. rm with -rf (needs BOTH recursive 'r'/'R' and force 'f')
    if exe == "rm":
        has_force = False
        has_recursive = False
        for token in tokens[1:]:
            if token.startswith("--"):
                if token == "--force":
                    has_force = True
                elif token == "--recursive":
                    has_recursive = True
            elif token.startswith("-") and len(token) > 1:
                flags = token[1:]
                if "f" in flags:
                    has_force = True
                if "r" in flags or "R" in flags:
                    has_recursive = True
        return has_force and has_recursive
        
    # 2. git checkout .
    if exe == "git" and len(tokens) >= 3 and tokens[1] == "checkout":
        return "." in tokens[2:]
        
    # 3. git reset --hard
    if exe == "git" and len(tokens) >= 3 and tokens[1] == "reset":
        return "--hard" in tokens[2:]
        
    # 4. git clean
    if exe == "git" and len(tokens) >= 2 and tokens[1] == "clean":
        return True
        
    return False

def verify_command(command: str) -> tuple[bool, str]:
    """
    Verifies if a command is safe to run.
    
    Checks if any subcommand or nested subshell is destructive:
    - rm with BOTH recursive and force flags (-rf, -r -f, etc.)
    - git checkout .
    - git reset --hard
    - git clean
    
    If it is destructive, it checks for unstaged changes in the git repository.
    If there are unstaged changes, it warns the user and returns False.
    Otherwise, returns True.
    """
    subcmds = get_subcommands(command)
    is_destructive = any(is_command_destructive(sub) for sub in subcmds)
    
    if is_destructive:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True
            )
            # Check if there are unstaged changes.
            unstaged_changes = False
            for line in result.stdout.splitlines():
                if len(line) >= 2 and line[1] != ' ':
                    unstaged_changes = True
                    break
            
            if unstaged_changes:
                return (
                    False,
                    "Warning: Running destructive command with unstaged changes. Please commit or stash your changes first."
                )
        except (subprocess.SubprocessError, FileNotFoundError):
            # If we are not in a git repository or git command is not found,
            # we cannot verify unstaged changes, so we treat it as safe.
            pass
            
    return (True, "Command verified safe.")

