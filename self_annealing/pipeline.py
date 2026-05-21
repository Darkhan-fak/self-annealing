import os
import shutil
import subprocess
import sys
import configparser

def _has_pyproject_section(sections: set, tool_prefix: str) -> bool:
    for s in sections:
        if s == tool_prefix or s.startswith(tool_prefix + "."):
            return True
    return False

def _detect_configured_sections(pyproject_path: str) -> set:
    sections = set()
    if not os.path.isfile(pyproject_path):
        return sections
        
    try:
        import tomllib
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        def walk(d, prefix=""):
            for k, v in d.items():
                name = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    sections.add(name)
                    walk(v, name)
        walk(data)
    except Exception:
        # Fallback to regex parser
        import re
        section_pat = re.compile(r'^\s*\[\s*([a-zA-Z0-9_\-\.]+)\s*\]\s*(?:#.*)?$')
        try:
            with open(pyproject_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m = section_pat.match(line)
                    if m:
                        sections.add(m.group(1))
        except Exception:
            pass
    return sections

def _has_ini_section(file_path: str, section: str) -> bool:
    if not os.path.isfile(file_path):
        return False
    parser = configparser.ConfigParser()
    try:
        parser.read(file_path)
        return section in parser.sections()
    except Exception:
        return False

def find_tool_executable(tool_name: str) -> list[str] | None:
    # First check PATH
    exec_path = shutil.which(tool_name)
    if exec_path:
        return [exec_path]
    
    # Second check if it can be run via active python interpreter
    try:
        result = subprocess.run(
            [sys.executable, "-m", tool_name, "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return [sys.executable, "-m", tool_name]
    except Exception:
        pass
        
    return None

def run_preflight_checks(project_dir: str) -> list[tuple[str, bool, str]]:
    """
    Run local pre-flight CI/CD checker on the specified project directory.
    
    Detects which formatters/linters are configured in the project or available
    in the environment, runs them in dry-run mode, and returns the results.
    
    Returns a list of tuples: (tool_name, passed_bool, output_message).
    """
    project_dir = os.path.abspath(project_dir)
    
    supported_tools = {
        "ruff": {
            "exec_name": "ruff",
            "check_args": ["check", "."],
            "config_files": ["ruff.toml", ".ruff.toml"],
            "pyproject_sections": ["tool.ruff"],
            "ini_sections": []
        },
        "black": {
            "exec_name": "black",
            "check_args": ["--check", "."],
            "config_files": [".black.toml", "black.toml"],
            "pyproject_sections": ["tool.black"],
            "ini_sections": []
        },
        "flake8": {
            "exec_name": "flake8",
            "check_args": ["."],
            "config_files": [".flake8", ".flake8rc"],
            "pyproject_sections": [],
            "ini_sections": ["flake8"]
        },
        "mypy": {
            "exec_name": "mypy",
            "check_args": ["."],
            "config_files": ["mypy.ini", ".mypy.ini"],
            "pyproject_sections": ["tool.mypy"],
            "ini_sections": ["mypy"]
        },
        "isort": {
            "exec_name": "isort",
            "check_args": ["--check-only", "."],
            "config_files": [".isort.cfg"],
            "pyproject_sections": ["tool.isort"],
            "ini_sections": ["isort"]
        },
        "pylint": {
            "exec_name": "pylint",
            "check_args": ["--recursive=y", "."],
            "config_files": [".pylintrc", "pylintrc"],
            "pyproject_sections": ["tool.pylint"],
            "ini_sections": ["pylint"]
        }
    }
    
    # 1. Parse pyproject.toml
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    pyproject_sections = _detect_configured_sections(pyproject_path)
    
    results = []
    
    for tool_name, info in supported_tools.items():
        is_configured = False
        
        # Check config files
        for config_file in info["config_files"]:
            if os.path.isfile(os.path.join(project_dir, config_file)):
                is_configured = True
                break
                
        # Check pyproject sections
        if not is_configured:
            for section in info["pyproject_sections"]:
                if _has_pyproject_section(pyproject_sections, section):
                    is_configured = True
                    break
                    
        # Check ini sections (setup.cfg, tox.ini)
        if not is_configured:
            for ini_file in ["setup.cfg", "tox.ini"]:
                ini_path = os.path.join(project_dir, ini_file)
                for section in info["ini_sections"]:
                    if _has_ini_section(ini_path, section):
                        is_configured = True
                        break
                if is_configured:
                    break
                    
        # Find tool executable
        tool_cmd = find_tool_executable(info["exec_name"])
        is_installed = tool_cmd is not None
        
        # Determine if we should check
        if is_configured or is_installed:
            if not is_installed:
                # Configured but not installed
                results.append((
                    tool_name,
                    False,
                    f"Tool '{tool_name}' is configured in the project but is not installed or available in the environment."
                ))
            else:
                # Installed and configured/available -> Run the check
                try:
                    full_cmd = tool_cmd + info["check_args"]
                    result = subprocess.run(
                        full_cmd,
                        cwd=project_dir,
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    passed = (result.returncode == 0)
                    output = (result.stdout or "") + (result.stderr or "")
                    results.append((tool_name, passed, output))
                except Exception as e:
                    results.append((
                        tool_name,
                        False,
                        f"Failed to run '{tool_name}': {str(e)}"
                    ))
                    
    return results
