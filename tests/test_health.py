import os
from pathlib import Path
import pytest
from self_annealing.health import (
    check_hc001,
    check_hc002,
    check_hc003,
    check_hc004,
    check_hc005,
    run_all_checks
)

def test_check_hc001_port_binding(tmp_path):
    # Case 1: Safe code
    safe_code = """
import os
port = int(os.environ.get("PORT", 8000))
app.run(port=port)
"""
    # Case 2: Violation code
    violation_code = """
app.run(port=8000)
"""
    
    # Write to safe file
    safe_dir = tmp_path / "safe"
    safe_dir.mkdir()
    (safe_dir / "app.py").write_text(safe_code, encoding='utf-8')
    
    passed, msg = check_hc001(safe_dir)
    assert passed is True
    
    # Write to violation file
    fail_dir = tmp_path / "fail"
    fail_dir.mkdir()
    (fail_dir / "app.py").write_text(violation_code, encoding='utf-8')
    
    passed, msg = check_hc001(fail_dir)
    assert passed is False
    assert "app.py:2" in msg

def test_check_hc002_gitignore(tmp_path):
    # Case 1: Valid .gitignore
    git_dir_ok = tmp_path / "git_ok"
    git_dir_ok.mkdir()
    (git_dir_ok / ".gitignore").write_text("# ignore env files\n.env.*\n.env\n", encoding='utf-8')
    
    passed, msg = check_hc002(git_dir_ok)
    assert passed is True
    
    # Case 2: Missing ignore
    git_dir_fail = tmp_path / "git_fail"
    git_dir_fail.mkdir()
    (git_dir_fail / ".gitignore").write_text("# ignore python build files\n__pycache__/\n", encoding='utf-8')
    
    passed, msg = check_hc002(git_dir_fail)
    assert passed is False
    
    # Case 3: Missing .gitignore
    git_dir_missing = tmp_path / "git_missing"
    git_dir_missing.mkdir()
    
    passed, msg = check_hc002(git_dir_missing)
    assert passed is False

def test_check_hc003_env_files(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    # Missing .env
    passed, msg = check_hc003(project_dir)
    assert passed is False
    assert "missing" in msg.lower()
    
    # Empty .env
    env_file = project_dir / ".env"
    env_file.touch()
    passed, msg = check_hc003(project_dir)
    assert passed is False
    assert "empty" in msg.lower()
    
    # Filled .env, missing .env.example
    env_file.write_text("API_KEY=dummy", encoding='utf-8')
    passed, msg = check_hc003(project_dir)
    assert passed is False
    assert "example" in msg.lower()
    
    # Both exist and valid
    env_example = project_dir / ".env.example"
    env_example.write_text("API_KEY=", encoding='utf-8')
    passed, msg = check_hc003(project_dir)
    assert passed is True

def test_check_hc004_requirements_or_pyproject(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    passed, msg = check_hc004(project_dir)
    assert passed is False
    
    (project_dir / "requirements.txt").touch()
    passed, msg = check_hc004(project_dir)
    assert passed is True
    
    # Remove requirements and create pyproject.toml
    (project_dir / "requirements.txt").unlink()
    (project_dir / "pyproject.toml").touch()
    passed, msg = check_hc004(project_dir)
    assert passed is True

def test_check_hc005_secret_scanner(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    # Safe code
    (project_dir / "app.py").write_text("API_KEY = os.environ.get('API_KEY')", encoding='utf-8')
    passed, msg = check_hc005(project_dir)
    assert passed is True
    
    # Anthropic key leak
    (project_dir / "app.py").write_text("anthropic_key = 'sk-ant-sid01-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqr'", encoding='utf-8')
    passed, msg = check_hc005(project_dir)
    assert passed is False
    assert "Anthropic API key" in msg
    
    # OpenAI key leak
    (project_dir / "app.py").write_text("openai_key = 'sk-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUV'", encoding='utf-8')
    passed, msg = check_hc005(project_dir)
    assert passed is False
    assert "OpenAI API key" in msg
    
    # Generic password leak
    (project_dir / "app.py").write_text("db_password = 'super_secret_pass_123'", encoding='utf-8')
    passed, msg = check_hc005(project_dir)
    assert passed is False
    assert "Generic secret" in msg

    # High-entropy raw key leak without regex matches
    (project_dir / "app.py").write_text("random_data = 'aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0'", encoding='utf-8')
    passed, msg = check_hc005(project_dir)
    assert passed is False
    assert "High-entropy secret" in msg
