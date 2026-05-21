import os
import re
from pathlib import Path

def check_hc001(project_root):
    """
    HC001: Check for hardcoded ports (3000, 5000, 8000, 8080) without environment variable fallback.
    """
    violations = []
    port_pattern = re.compile(r'\b(3000|5000|8000|8080)\b')
    
    for root, dirs, files in os.walk(project_root):
        # Exclude common non-project directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', 'venv2', '.venv', 'build', 'dist', 'self_annealing.egg-info', 'node_modules', 'tests', 'demo')]
        
        for file in files:
            if not file.endswith('.py'):
                continue
            
            file_path = Path(root) / file
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line_num, line in enumerate(f, 1):
                        # Skip comment lines
                        if line.strip().startswith('#'):
                            continue
                        
                        if port_pattern.search(line):
                            line_lower = line.lower()
                            # Check if the line has env fallback configuration
                            if not ('environ' in line_lower or 'getenv' in line_lower or 'env' in line_lower):
                                relative_path = file_path.relative_to(project_root)
                                violations.append(f"{relative_path}:{line_num} (line: {line.strip()})")
            except Exception:
                pass
                
    if violations:
        return False, "Hardcoded port binding found without env configuration in:\n  " + "\n  ".join(violations)
    return True, "PORT binding to $PORT is correct."

def check_hc002(project_root):
    """
    HC002: Check if .env files are correctly ignored in .gitignore.
    """
    gitignore_path = Path(project_root) / ".gitignore"
    if not gitignore_path.exists():
        return False, ".gitignore file does not exist."
    
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line in lines:
            line_clean = line.strip()
            # Ignore comments and empty lines
            if not line_clean or line_clean.startswith('#'):
                continue
            
            # Check if line matches .env or standard wildcard ignores
            if line_clean in (".env", ".env.*", ".env*", ".env.local"):
                return True, ".env is correctly ignored in .gitignore."
    except Exception as e:
        return False, f"Error reading .gitignore: {str(e)}"
        
    return False, ".env or .env.* is not ignored in .gitignore."

def check_hc003(project_root):
    """
    HC003: Check if .env file exists and is not empty, and .env.example exists.
    """
    env_path = Path(project_root) / ".env"
    env_example_path = Path(project_root) / ".env.example"
    
    if not env_path.exists():
        return False, ".env file is missing."
        
    if env_path.stat().st_size == 0:
        return False, ".env file is empty."
        
    if not env_example_path.exists():
        return False, ".env.example file is missing."
        
    return True, ".env exists, is not empty, and .env.example exists."

def check_hc004(project_root):
    """
    HC004: Check if requirements.txt or pyproject.toml exists in the project root.
    """
    req_path = Path(project_root) / "requirements.txt"
    pyproj_path = Path(project_root) / "pyproject.toml"
    
    if req_path.exists() or pyproj_path.exists():
        return True, "requirements.txt or pyproject.toml exists."
    return False, "Neither requirements.txt nor pyproject.toml was found in project root."

def calculate_shannon_entropy(s: str) -> float:
    """
    Calculates the Shannon Entropy of a string.
    """
    if not s:
        return 0.0
    import math
    from collections import Counter
    total_len = len(s)
    counts = Counter(s)
    entropy = 0.0
    for count in counts.values():
        p = count / total_len
        entropy -= p * math.log2(p)
    return entropy

def extract_potential_secrets(line: str, is_env: bool) -> list[str]:
    """
    Extracts potential secrets from a line:
    - Quoted string literals (single/double quotes)
    - For .env files, the RHS of assignments (stripped and unquoted)
    """
    secrets = []
    # 1. Match quoted strings
    quoted_pattern = re.compile(r'(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\')')
    for match in quoted_pattern.finditer(line):
        val = match.group(1) or match.group(2)
        if val:
            secrets.append(val)
            
    # 2. In .env files, check the RHS of '='
    if is_env and '=' in line:
        parts = line.split('=', 1)
        val = parts[1].strip()
        # strip comment
        val_no_comment = val.split('#', 1)[0].strip()
        # strip quotes if any
        if (val_no_comment.startswith('"') and val_no_comment.endswith('"')) or \
           (val_no_comment.startswith("'") and val_no_comment.endswith("'")):
            val_no_comment = val_no_comment[1:-1]
        if val_no_comment:
            secrets.append(val_no_comment)
            
    return list(set(secrets))

def check_hc005(project_root):
    """
    HC005: Scan for hardcoded API keys and secrets in .py and .env files.
    Includes regex checking and Shannon Entropy calculation for raw key strings.
    """
    anthropic_pattern = re.compile(r'sk-ant-sid\d+-[a-zA-Z0-9_\-]{80,}')
    openai_pattern = re.compile(r'sk-[a-zA-Z0-9]{48,}')
    generic_pattern = re.compile(r'(password|token|secret|key)\s*=\s*[\'"]([a-zA-Z0-9_\-]{8,})[\'"]', re.IGNORECASE)
    
    violations = []
    
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', 'venv2', '.venv', 'build', 'dist', 'self_annealing.egg-info', 'node_modules', 'tests', 'demo')]
        
        for file in files:
            # Check only .py and .env files (or files starting with .env but not ending in .example or .sample)
            is_py = file.endswith('.py')
            is_env = (file == '.env' or file.startswith('.env.')) and not (file.endswith('.example') or file.endswith('.sample'))
            
            if not (is_py or is_env):
                continue
                
            file_path = Path(root) / file
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line_num, line in enumerate(f, 1):
                        line_str = line.strip()
                        relative_path = file_path.relative_to(project_root)
                        
                        # 1. Check Anthropic
                        if anthropic_pattern.search(line_str):
                            violations.append(f"Anthropic API key in {relative_path}:{line_num}")
                            continue
                            
                        # 2. Check OpenAI
                        if openai_pattern.search(line_str):
                            violations.append(f"OpenAI API key in {relative_path}:{line_num}")
                            continue
                            
                        # 3. Check Generic secret
                        if generic_pattern.search(line_str):
                            violations.append(f"Generic secret in {relative_path}:{line_num}")
                            continue
                            
                        # 4. Check Shannon Entropy for high-entropy strings
                        potential_secrets = extract_potential_secrets(line_str, is_env)
                        found_entropy_violation = False
                        for secret in potential_secrets:
                            if len(secret) > 20:
                                entropy = calculate_shannon_entropy(secret)
                                if entropy > 4.5:
                                    violations.append(f"High-entropy secret ({entropy:.2f}) in {relative_path}:{line_num}")
                                    found_entropy_violation = True
                                    break
                        if found_entropy_violation:
                            continue
            except Exception:
                pass
                
    if violations:
        return False, "Hardcoded secrets found:\n  " + "\n  ".join(violations)
    return True, "No secrets found."

def run_all_checks(project_root):
    """
    Runs all 5 health checks and returns a dict mapping check ID to (passed, message).
    """
    return {
        'HC001': check_hc001(project_root),
        'HC002': check_hc002(project_root),
        'HC003': check_hc003(project_root),
        'HC004': check_hc004(project_root),
        'HC005': check_hc005(project_root),
    }
