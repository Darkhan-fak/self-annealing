import os
import sys
import shutil
import subprocess
from unittest.mock import patch, MagicMock
from self_annealing.pipeline import run_preflight_checks

def get_subprocess_mock(installed_tools=None, run_stdout="Success", run_stderr="", run_returncode=0):
    if installed_tools is None:
        installed_tools = []
        
    def mock_run(args, **kwargs):
        mock_res = MagicMock()
        # Differentiate version check (sys.executable -m <tool> --version) vs actual check run
        is_version_check = (
            len(args) >= 4 
            and args[0] == sys.executable 
            and args[1] == "-m" 
            and args[3] == "--version"
        )
        if is_version_check:
            tool = args[2]
            if tool in installed_tools:
                mock_res.returncode = 0
                mock_res.stdout = f"{tool} 1.0"
                mock_res.stderr = ""
            else:
                mock_res.returncode = 1
                mock_res.stdout = ""
                mock_res.stderr = "No module found"
        else:
            mock_res.returncode = run_returncode
            mock_res.stdout = run_stdout
            mock_res.stderr = run_stderr
        return mock_res
    return mock_run

def test_no_tools_configured_or_installed(tmp_path):
    with patch("shutil.which", return_value=None), \
         patch("subprocess.run", side_effect=get_subprocess_mock([])):
        results = run_preflight_checks(str(tmp_path))
        assert results == []

def test_tool_configured_but_not_installed(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.black]\nline-length = 88", encoding="utf-8")
    
    with patch("shutil.which", return_value=None), \
         patch("subprocess.run", side_effect=get_subprocess_mock([])):
        results = run_preflight_checks(str(tmp_path))
        
        assert len(results) == 1
        tool, passed, msg = results[0]
        assert tool == "black"
        assert passed is False
        assert "configured in the project but is not installed" in msg

def test_tool_configured_and_installed_passing(tmp_path):
    ruff_toml = tmp_path / "ruff.toml"
    ruff_toml.write_text("", encoding="utf-8")
    
    with patch("shutil.which", side_effect=lambda x: f"/bin/{x}" if x == "ruff" else None), \
         patch("subprocess.run", side_effect=get_subprocess_mock(["ruff"], run_stdout="Ruff passed!")):
        
        results = run_preflight_checks(str(tmp_path))
        
        assert len(results) == 1
        tool, passed, msg = results[0]
        assert tool == "ruff"
        assert passed is True
        assert "Ruff passed!" in msg

def test_tool_configured_and_installed_failing(tmp_path):
    setup_cfg = tmp_path / "setup.cfg"
    setup_cfg.write_text("[flake8]\nmax-line-length = 120", encoding="utf-8")
    
    with patch("shutil.which", side_effect=lambda x: f"/bin/{x}" if x == "flake8" else None), \
         patch("subprocess.run", side_effect=get_subprocess_mock(["flake8"], run_stderr="Line too long", run_returncode=1)):
         
        results = run_preflight_checks(str(tmp_path))
        
        assert len(results) == 1
        tool, passed, msg = results[0]
        assert tool == "flake8"
        assert passed is False
        assert "Line too long" in msg

def test_tool_not_configured_but_installed(tmp_path):
    with patch("shutil.which", side_effect=lambda x: f"/bin/{x}" if x == "black" else None), \
         patch("subprocess.run", side_effect=get_subprocess_mock(["black"], run_stdout="Everything formatted!")):
         
        results = run_preflight_checks(str(tmp_path))
        
        assert len(results) == 1
        tool, passed, msg = results[0]
        assert tool == "black"
        assert passed is True
        assert "Everything formatted!" in msg

def test_multiple_tools_detected(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.black]\n", encoding="utf-8")
    ruff_toml = tmp_path / "ruff.toml"
    ruff_toml.write_text("\n", encoding="utf-8")
    
    def mock_which(cmd):
        if cmd in ("ruff", "black"):
            return f"/bin/{cmd}"
        return None
        
    with patch("shutil.which", side_effect=mock_which), \
         patch("subprocess.run", side_effect=get_subprocess_mock(["ruff", "black"], run_stdout="Success")):
         
        results = run_preflight_checks(str(tmp_path))
        
        results_sorted = sorted(results, key=lambda x: x[0])
        assert len(results_sorted) == 2
        
        assert results_sorted[0][0] == "black"
        assert results_sorted[0][1] is True
        assert results_sorted[0][2] == "Success"
        
        assert results_sorted[1][0] == "ruff"
        assert results_sorted[1][1] is True
        assert results_sorted[1][2] == "Success"
