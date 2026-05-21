import subprocess
from unittest.mock import patch, MagicMock
import pytest
from self_annealing.safety import verify_command

def test_non_destructive_command():
    # Non-destructive commands should return safe immediately without checking git status
    with patch("subprocess.run") as mock_run:
        success, msg = verify_command("ls -la")
        assert success is True
        assert msg == "Command verified safe."
        mock_run.assert_not_called()

def test_destructive_command_clean_repo():
    # Destructive command when repository is clean (git status --porcelain is empty)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        success, msg = verify_command("rm -rf tmp/")
        assert success is True
        assert msg == "Command verified safe."
        mock_run.assert_called_once_with(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)

def test_destructive_command_with_unstaged_modifications():
    # Destructive command when git status shows unstaged modification (' M')
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=" M file.py\n", stderr="", returncode=0)
        success, msg = verify_command("git reset --hard")
        assert success is False
        assert "unstaged changes" in msg
        mock_run.assert_called_once()

def test_destructive_command_with_untracked_files():
    # Destructive command when git status shows untracked files ('??')
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="?? untracked.py\n", stderr="", returncode=0)
        success, msg = verify_command("git clean -fd")
        assert success is False
        assert "unstaged changes" in msg
        mock_run.assert_called_once()

def test_destructive_command_with_staged_only_changes():
    # Destructive command when git status shows ONLY staged changes ('M ')
    # Y is ' ', so no unstaged changes.
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="M  staged.py\n", stderr="", returncode=0)
        success, msg = verify_command("git checkout .")
        assert success is True
        assert msg == "Command verified safe."
        mock_run.assert_called_once()

def test_destructive_command_with_both_staged_and_unstaged_changes():
    # Destructive command when git status shows both staged ('M ') and unstaged (' M')
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="M  staged.py\n M unstaged.py\n", stderr="", returncode=0)
        success, msg = verify_command("git checkout .")
        assert success is False
        assert "unstaged changes" in msg
        mock_run.assert_called_once()

def test_destructive_command_git_error():
    # If git command fails (e.g. not in a git repo), treat as safe
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git status --porcelain")
        success, msg = verify_command("git clean")
        assert success is True
        assert msg == "Command verified safe."
        mock_run.assert_called_once()

def test_destructive_command_git_missing():
    # If git is not installed, treat as safe
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        success, msg = verify_command("git clean")
        assert success is True
        assert msg == "Command verified safe."
        mock_run.assert_called_once()

def test_chained_safety_checks():
    # Test that shell operators split commands and catch destructive actions in any part
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=" M file.py\n", stderr="", returncode=0)
        
        # Destructive command at the end of a chain
        success, msg = verify_command("ls -la && git clean")
        assert success is False
        
        # Destructive command at the start of a chain
        success, msg = verify_command("git reset --hard || echo 'reset failed'")
        assert success is False
        
        # Destructive command in the middle
        success, msg = verify_command("echo 'hello'; rm -rf tmp/; echo 'done'")
        assert success is False

def test_nested_subshell_safety_checks():
    # Test nested command execution / subshells
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="?? untracked.py\n", stderr="", returncode=0)
        
        # $(...) subshell containing destructive command
        success, msg = verify_command("echo $(rm -rf /tmp/test)")
        assert success is False
        
        # `...` subshell containing destructive command
        success, msg = verify_command("echo `git clean`")
        assert success is False
        
        # Nested subshells
        success, msg = verify_command("echo $(echo `rm -rf /`)")
        assert success is False

def test_tokenization_and_false_positives():
    # Test that false positives (e.g. echo rm -rf) are avoided, and bypasses are caught
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=" M file.py\n", stderr="", returncode=0)
        
        # False positive: rm -rf is an argument to echo, not the executable
        success, msg = verify_command("echo rm -rf")
        assert success is True
        
        # Bypasses: space separation and flag combinations
        success, msg = verify_command("rm -r -f dir")
        assert success is False
        
        # Path prefix bypasses
        success, msg = verify_command("/usr/bin/rm -rf dir")
        assert success is False
        
        success, msg = verify_command("git.exe clean")
        assert success is False

