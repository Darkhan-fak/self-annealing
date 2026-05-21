import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from self_annealing.git_helper import (
    find_error_log,
    get_git_status,
    suggest_commit_message
)

def test_find_error_log(tmp_path):
    # Case 1: error_log.md at root
    project_dir_1 = tmp_path / "proj1"
    project_dir_1.mkdir()
    log_file_1 = project_dir_1 / "error_log.md"
    log_file_1.touch()
    
    found = find_error_log(str(project_dir_1))
    assert found is not None
    assert Path(found).resolve() == log_file_1.resolve()
    
    # Case 2: error_log.md in a subdirectory
    project_dir_2 = tmp_path / "proj2"
    project_dir_2.mkdir()
    sub_dir = project_dir_2 / "src"
    sub_dir.mkdir()
    log_file_2 = sub_dir / "error_log.md"
    log_file_2.touch()
    
    found = find_error_log(str(project_dir_2))
    assert found is not None
    assert Path(found).resolve() == log_file_2.resolve()
    
    # Case 3: Prefer non-templates path over templates path
    project_dir_3 = tmp_path / "proj3"
    project_dir_3.mkdir()
    templates_dir = project_dir_3 / "templates"
    templates_dir.mkdir()
    template_log = templates_dir / "error_log.md"
    template_log.touch()
    
    real_dir = project_dir_3 / "real"
    real_dir.mkdir()
    real_log = real_dir / "error_log.md"
    real_log.touch()
    
    found = find_error_log(str(project_dir_3))
    assert found is not None
    assert Path(found).resolve() == real_log.resolve()

    # Case 4: No error_log.md at all
    project_dir_4 = tmp_path / "proj4"
    project_dir_4.mkdir()
    found = find_error_log(str(project_dir_4))
    assert found is None

def test_get_git_status():
    # Test normal git status parsing
    mock_stdout = " M self_annealing/git_helper.py\n?? tests/test_git_helper.py\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout)
        files = get_git_status("dummy_path")
        assert files == ["self_annealing/git_helper.py", "tests/test_git_helper.py"]
        mock_run.assert_called_once_with(
            ["git", "status", "--porcelain"],
            cwd="dummy_path",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

    # Test when git command fails or is missing
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
        files = get_git_status("dummy_path")
        assert files == []

    with patch("subprocess.run", side_effect=FileNotFoundError):
        files = get_git_status("dummy_path")
        assert files == []

def test_suggest_commit_message_fallback(tmp_path):
    # No error log
    with patch("self_annealing.git_helper.get_git_status") as mock_status:
        mock_status.return_value = ["file1.py", "file2.py"]
        msg = suggest_commit_message(str(tmp_path))
        assert "chore: update project files" in msg
        assert "- file1.py" in msg
        assert "- file2.py" in msg

def test_suggest_commit_message_with_log(tmp_path):
    # Setup a dummy error_log.md
    log_content = """# Error Log

## Error E101
- **Symptom**: Connection timeout to server
- **Cause**: Port 8080 was blocked by firewall
- **Fix**: Open port 8080 or change to 80
- **Context**: network
- **Tokens**: 120
"""
    log_file = tmp_path / "error_log.md"
    log_file.write_text(log_content, encoding="utf-8")
    
    with patch("self_annealing.git_helper.get_git_status") as mock_status:
        mock_status.return_value = ["src/api.py"]
        
        msg = suggest_commit_message(str(tmp_path))
        
        # Check expected conventional commit format: fix(scope): summary
        assert "fix(network): open port 8080 or change to 80" in msg
        assert "Symptom: Connection timeout to server" in msg
        assert "Cause: Port 8080 was blocked by firewall" in msg
        assert "Fix: Open port 8080 or change to 80" in msg
        assert "- src/api.py" in msg

def test_suggest_commit_message_long_fix(tmp_path):
    log_content = """# Error Log

## Error E102
- **Symptom**: Out of memory error
- **Cause**: Reading huge files into memory at once
- **Fix**: Use generators to stream large text files instead of reading them with readlines() at once to prevent consuming all system RAM
- **Context**: performance
- **Tokens**: 300
"""
    log_file = tmp_path / "error_log.md"
    log_file.write_text(log_content, encoding="utf-8")
    
    with patch("self_annealing.git_helper.get_git_status") as mock_status:
        mock_status.return_value = ["src/loader.py"]
        
        msg = suggest_commit_message(str(tmp_path))
        
        # Check the first line of the commit message (the title)
        first_line = msg.splitlines()[0]
        assert first_line.startswith("fix(performance): use generators to stream large")
        assert first_line.endswith("...")
        assert len(first_line) < 80

def test_suggest_commit_message_empty_fields(tmp_path):
    log_content = """# Error Log

## Error E103
- **Symptom**: 
- **Cause**: 
- **Fix**: 
"""
    log_file = tmp_path / "error_log.md"
    log_file.write_text(log_content, encoding="utf-8")
    
    with patch("self_annealing.git_helper.get_git_status") as mock_status:
        mock_status.return_value = []
        msg = suggest_commit_message(str(tmp_path))
        # It should fallback to core context and generic fix description
        assert "fix(core): fix error described in log" in msg
