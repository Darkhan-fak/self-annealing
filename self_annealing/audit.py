import os
import re
import subprocess
from pathlib import Path

class GitignoreMatcher:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.rules = []
        gitignore_path = root_dir / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        negated = False
                        if line.startswith('!'):
                            negated = True
                            line = line[1:]
                        try:
                            regex = self._compile_pattern(line)
                            self.rules.append((regex, negated))
                        except Exception:
                            pass
            except Exception:
                pass

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        is_dir_only = pattern.endswith('/')
        if is_dir_only:
            pattern = pattern[:-1]
            
        from_root = pattern.startswith('/')
        if from_root:
            pattern = pattern[1:]
            
        contains_slash = '/' in pattern
        
        regex_parts = []
        i = 0
        n = len(pattern)
        while i < n:
            char = pattern[i]
            if char == '*':
                if i + 1 < n and pattern[i+1] == '*':
                    # It's '**'
                    is_start = (i == 0)
                    is_end = (i + 2 == n)
                    left_slash = (i > 0 and pattern[i-1] == '/')
                    right_slash = (i + 2 < n and pattern[i+2] == '/')
                    
                    if (is_start or left_slash) and (is_end or right_slash):
                        regex_parts.append(r'.*')
                        i += 2
                        if i < n and pattern[i] == '/':
                            i += 1
                        continue
                    else:
                        regex_parts.append(r'[^/]*')
                        i += 2
                else:
                    regex_parts.append(r'[^/]*')
                    i += 1
            elif char == '?':
                regex_parts.append(r'[^/]')
                i += 1
            elif char in r'.+^${}()|[\]\\':
                regex_parts.append('\\' + char)
                i += 1
            elif char == '/':
                regex_parts.append(r'/')
                i += 1
            else:
                regex_parts.append(char)
                i += 1
                
        regex_str = "".join(regex_parts)
        
        if not (from_root or contains_slash):
            regex_str = r'(?:^|.*/)' + regex_str
        else:
            regex_str = r'^' + regex_str
            
        regex_str = regex_str + r'(?:$|/.*)'
        return re.compile(regex_str)

    def is_ignored(self, file_path: Path) -> bool:
        try:
            rel_path = file_path.relative_to(self.root_dir)
        except ValueError:
            return False
            
        # Check parents first
        parents = list(rel_path.parents)
        parents.reverse()
        for parent in parents:
            if parent == Path('.'):
                continue
            parent_str = parent.as_posix()
            parent_ignored = False
            for regex, negated in self.rules:
                if regex.match(parent_str):
                    parent_ignored = not negated
            if parent_ignored:
                return True
                
        # Check the file itself
        rel_str = rel_path.as_posix()
        ignored = False
        for regex, negated in self.rules:
            if regex.match(rel_str):
                ignored = not negated
        return ignored


def check_ignored_files(root_path: Path, file_paths: list[Path]) -> set[Path]:
    ignored = set()
    git_success = False
    
    # Try git command first
    try:
        # Check if the folder is inside a git repository
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(root_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            rel_paths = []
            path_map = {}
            for p in file_paths:
                try:
                    rel = p.relative_to(root_path)
                    rel_str = rel.as_posix()
                    rel_paths.append(rel_str)
                    path_map[rel_str] = p
                except ValueError:
                    pass
            
            if rel_paths:
                # Run git check-ignore --stdin -z
                input_bytes = "\x00".join(rel_paths).encode('utf-8')
                process = subprocess.Popen(
                    ["git", "check-ignore", "--stdin", "-z"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(root_path)
                )
                stdout, stderr = process.communicate(input=input_bytes)
                if process.returncode in (0, 1):
                    git_success = True
                    ignored_rel_strs = [p.decode('utf-8') for p in stdout.split(b'\x00') if p]
                    for r in ignored_rel_strs:
                        if r in path_map:
                            ignored.add(path_map[r])
    except Exception:
        git_success = False
        
    if not git_success:
        # Fallback to manual gitignore matcher
        matcher = GitignoreMatcher(root_path)
        ignored = {p for p in file_paths if matcher.is_ignored(p)}
        
    return ignored


def audit_large_files(root_dir: str) -> list[dict]:
    """
    Scan the project directory recursively and identify files larger than 100KB.
    Check if each large file is matched by any rule in .gitignore.
    Return a list of dicts for non-ignored large files containing path, size, and warning message.
    """
    root_path = Path(root_dir).resolve()
    large_files = []
    
    # Scan project directory recursively
    for root, dirs, files in os.walk(root_path):
        # Exclude the internal .git directory
        if '.git' in dirs:
            dirs.remove('.git')
            
        for file in files:
            file_path = Path(root) / file
            try:
                # Get file size in bytes
                size = file_path.stat().st_size
                if size > 102400:  # 100KB
                    large_files.append((file_path, size))
            except (OSError, FileNotFoundError):
                continue
                
    if not large_files:
        return []
        
    # Check ignored status
    file_paths = [p for p, _ in large_files]
    ignored_paths = check_ignored_files(root_path, file_paths)
    
    results = []
    for file_path, size in large_files:
        if file_path not in ignored_paths:
            # Generate a helpful warning message
            rel_path = file_path.relative_to(root_path)
            warning_msg = f"File '{rel_path}' is large ({size / 1024:.2f}KB) and is not ignored by .gitignore."
            results.append({
                "path": str(file_path),
                "size": size,
                "warning": warning_msg
            })
            
    return results
