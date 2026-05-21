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
