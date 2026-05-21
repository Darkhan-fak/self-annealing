import subprocess

def verify_command(command: str) -> tuple[bool, str]:
    """
    Verifies if a command is safe to run.
    
    Checks if the command is destructive (contains patterns like 'rm -rf', 
    'git reset --hard', 'git checkout .', 'git clean').
    If it is destructive, it checks for unstaged changes in the git repository.
    If there are unstaged changes, it warns the user and returns False.
    Otherwise, returns True.
    """
    destructive_patterns = ["rm -rf", "git reset --hard", "git checkout .", "git clean"]
    is_destructive = any(pattern in command for pattern in destructive_patterns)
    
    if is_destructive:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True
            )
            # Check if there are unstaged changes.
            # git status --porcelain output lines have the format:
            # XY PATH
            # where X represents the index (staged) and Y represents the worktree (unstaged).
            # If Y is not a space (' '), it indicates an unstaged change (including untracked files '??').
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
