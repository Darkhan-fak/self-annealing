import pathlib
from unittest.mock import patch, MagicMock
import pytest
import importlib.metadata

from self_annealing.dependencies import (
    check_dependencies,
    parse_dependency_specifier,
    parse_requirements_txt,
    parse_pyproject_toml,
    compare_versions,
    evaluate_marker_fallback,
    normalize_name
)

def test_normalize_name():
    assert normalize_name("PyTest_Cov.Mock") == "pytest-cov-mock"
    assert normalize_name("numpy") == "numpy"

def test_parse_dependency_specifier():
    # Simple package
    name, specs, marker = parse_dependency_specifier("colorama")
    assert name == "colorama"
    assert specs == []
    assert marker == ""

    # Package with simple specifier
    name, specs, marker = parse_dependency_specifier("numpy>=1.21.0")
    assert name == "numpy"
    assert specs == [(">=", "1.21.0")]
    assert marker == ""

    # Package with multiple specifiers and markers
    name, specs, marker = parse_dependency_specifier("requests[security] >= 2.25.1, < 3.0.0; python_version >= '3.6'")
    assert name == "requests"
    assert specs == [(">=", "2.25.1"), ("<", "3.0.0")]
    assert marker == "python_version >= '3.6'"

    # Package with direct reference
    name, specs, marker = parse_dependency_specifier("pytest @ git+https://github.com/pytest-dev/pytest.git")
    assert name == "pytest"
    assert specs == [("@", "git+https://github.com/pytest-dev/pytest.git")]
    assert marker == ""

def test_parse_requirements_txt():
    content = """
    # Requirements file comment
    numpy>=1.20
    
    -r other-requirements.txt
    colorama >= 0.4.6 # inline comment here
    
    pytest --editable
    """
    deps = parse_requirements_txt(content)
    assert deps == ["numpy>=1.20", "colorama >= 0.4.6", "pytest"]

def test_parse_pyproject_toml():
    content = """
    [project]
    name = "test-project"
    dependencies = [
        "colorama>=0.4.6",
        "mcp>=1.0.0",
        'pytest'
    ]
    """
    deps = parse_pyproject_toml(content)
    assert deps == ["colorama>=0.4.6", "mcp>=1.0.0", "pytest"]

    # Test single line array
    content_single = """
    [project]
    dependencies = ["numpy", "pandas>=1.0"]
    """
    deps_single = parse_pyproject_toml(content_single)
    assert deps_single == ["numpy", "pandas>=1.0"]

def test_compare_versions():
    # Basic matches
    assert compare_versions("1.2.3", "==", "1.2.3")
    assert not compare_versions("1.2.3", "==", "1.2.4")
    assert compare_versions("1.2.3", "!=", "1.2.4")

    # Greater / Less than
    assert compare_versions("1.2.3", ">=", "1.2.0")
    assert compare_versions("1.2.3", ">=", "1.2.3")
    assert not compare_versions("1.2.3", ">=", "1.2.4")
    assert compare_versions("1.2.3", ">", "1.2")
    assert compare_versions("1.2", "<", "1.2.3")

    # Compatible release ~=
    # ~= 1.2.3 is >= 1.2.3, < 1.3.0
    assert compare_versions("1.2.3", "~=", "1.2.3")
    assert compare_versions("1.2.5", "~=", "1.2.3")
    assert not compare_versions("1.3.0", "~=", "1.2.3")
    assert not compare_versions("1.2.2", "~=", "1.2.3")

    # ~= 1.2 is >= 1.2, < 2.0
    assert compare_versions("1.2.5", "~=", "1.2")
    assert compare_versions("1.9.0", "~=", "1.2")
    assert not compare_versions("2.0.0", "~=", "1.2")

def test_evaluate_marker_fallback():
    # Empty marker should evaluate to True
    assert evaluate_marker_fallback("")
    
    # Simple matches using sys_platform
    with patch("sys.platform", "win32"), patch("os.name", "nt"):
        assert evaluate_marker_fallback("sys_platform == 'win32'")
        assert not evaluate_marker_fallback("sys_platform == 'linux'")
        assert evaluate_marker_fallback("sys_platform != 'linux'")
        assert evaluate_marker_fallback("os_name == 'nt'")

    # Complex boolean combinations
    with patch("sys.platform", "linux"):
        assert evaluate_marker_fallback("sys_platform == 'linux' or sys_platform == 'win32'")
        assert not evaluate_marker_fallback("sys_platform == 'win32' or sys_platform == 'darwin'")

def test_check_dependencies_no_files(tmp_path):
    # No files present
    errors = check_dependencies(str(tmp_path))
    assert len(errors) == 1
    assert "No requirements.txt or pyproject.toml found" in errors[0]

def test_check_dependencies_missing_package(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("missing-package-demo>=1.0.0\n", encoding="utf-8")

    # Mock get_installed_version to return None
    with patch("self_annealing.dependencies.get_installed_version", return_value=None):
        errors = check_dependencies(str(tmp_path))
        assert len(errors) == 1
        assert "Package 'missing-package-demo' is declared but not installed." in errors[0]

def test_check_dependencies_version_mismatch(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("demo-pkg>=2.0.0\n", encoding="utf-8")

    # Mock get_installed_version to return older version
    with patch("self_annealing.dependencies.get_installed_version", return_value="1.5.0"):
        errors = check_dependencies(str(tmp_path))
        assert len(errors) == 1
        assert "version mismatch" in errors[0]
        assert "installed '1.5.0', but require '>=2.0.0'" in errors[0]

def test_check_dependencies_version_match(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("demo-pkg>=2.0.0\n", encoding="utf-8")

    # Mock get_installed_version to return compatible version
    with patch("self_annealing.dependencies.get_installed_version", return_value="2.3.1"):
        errors = check_dependencies(str(tmp_path))
        assert len(errors) == 0

def test_check_dependencies_marker_skip(tmp_path):
    req_file = tmp_path / "requirements.txt"
    # Marker specifies an OS that won't match
    req_file.write_text("some-pkg>=1.0.0; sys_platform == 'nonexistent-os'\n", encoding="utf-8")

    # Mock sys.platform to be something else, and package not installed
    with patch("sys.platform", "linux"), patch("self_annealing.dependencies.get_installed_version", return_value=None):
        errors = check_dependencies(str(tmp_path))
        # It should skip checking because marker does not apply
        assert len(errors) == 0

def test_check_dependencies_direct_reference(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("demo-pkg @ git+https://github.com/foo/demo-pkg.git\n", encoding="utf-8")

    # Mock package to be installed
    with patch("self_annealing.dependencies.get_installed_version", return_value="1.0.0+local"):
        errors = check_dependencies(str(tmp_path))
        assert len(errors) == 0
