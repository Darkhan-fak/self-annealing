import os
import subprocess
from pathlib import Path
import pytest
from self_annealing.audit import audit_large_files, GitignoreMatcher

def test_audit_no_large_files(tmp_path):
    # Create small files (less than 100KB)
    (tmp_path / "small1.txt").write_bytes(b"a" * 1000)
    (tmp_path / "small2.txt").write_bytes(b"b" * 102400) # exactly 100KB (not strictly larger than 100KB)
    
    results = audit_large_files(str(tmp_path))
    assert results == []

def test_audit_large_files_no_gitignore(tmp_path):
    # Create a large file (strictly larger than 100KB)
    large_size = 102400 + 1
    (tmp_path / "large.txt").write_bytes(b"c" * large_size)
    
    results = audit_large_files(str(tmp_path))
    assert len(results) == 1
    assert results[0]["path"] == str((tmp_path / "large.txt").resolve())
    assert results[0]["size"] == large_size
    assert "large.txt" in results[0]["warning"]

def test_audit_ignored_large_files_fallback(tmp_path):
    # No git repo initialized, will test the Python fallback matcher
    # Create a .gitignore file
    (tmp_path / ".gitignore").write_text("\n".join([
        "*.log",
        "large_dir/",
        "build/*",
        "!build/important.txt"
    ]), encoding='utf-8')
    
    # Create files larger than 100KB
    large_size = 105000
    
    # 1. Ignored by *.log
    (tmp_path / "ignored1.log").write_bytes(b"x" * large_size)
    
    # 2. Ignored by large_dir/
    large_dir = tmp_path / "large_dir"
    large_dir.mkdir()
    (large_dir / "ignored2.txt").write_bytes(b"y" * large_size)
    
    # 3. Ignored by build/*
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "ignored3.txt").write_bytes(b"z" * large_size)
    
    # 4. Negated (not ignored) by !build/important.txt
    important_file = build_dir / "important.txt"
    important_file.write_bytes(b"w" * large_size)
    
    # 5. Not ignored
    keep_file = tmp_path / "keep.txt"
    keep_file.write_bytes(b"k" * large_size)
    
    results = audit_large_files(str(tmp_path))
    
    # We expect keep_file and important_file to be reported because they are not ignored.
    # The others should be filtered out by the gitignore fallback matcher.
    reported_paths = {r["path"] for r in results}
    expected_paths = {
        str(keep_file.resolve()),
        str(important_file.resolve())
    }
    assert reported_paths == expected_paths

def test_audit_ignored_large_files_git(tmp_path):
    # Initialize git repo in the temp path to test the Git subprocess integration
    try:
        subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:
        pytest.skip("Git command line tool not available")
        
    # Create a .gitignore file
    (tmp_path / ".gitignore").write_text("\n".join([
        "*.log",
        "large_dir/",
        "build/*",
        "!build/important.txt"
    ]), encoding='utf-8')
    
    # Create files larger than 100KB
    large_size = 105000
    
    # 1. Ignored by *.log
    (tmp_path / "ignored1.log").write_bytes(b"x" * large_size)
    
    # 2. Ignored by large_dir/
    large_dir = tmp_path / "large_dir"
    large_dir.mkdir()
    (large_dir / "ignored2.txt").write_bytes(b"y" * large_size)
    
    # 3. Ignored by build/*
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "ignored3.txt").write_bytes(b"z" * large_size)
    
    # 4. Negated (not ignored) by !build/important.txt
    important_file = build_dir / "important.txt"
    important_file.write_bytes(b"w" * large_size)
    
    # 5. Not ignored
    keep_file = tmp_path / "keep.txt"
    keep_file.write_bytes(b"k" * large_size)
    
    results = audit_large_files(str(tmp_path))
    
    reported_paths = {r["path"] for r in results}
    expected_paths = {
        str(keep_file.resolve()),
        str(important_file.resolve())
    }
    assert reported_paths == expected_paths

def test_gitignore_matcher_rules(tmp_path):
    (tmp_path / ".gitignore").write_text("\n".join([
        "*.log",
        "build/",
        "!build/important.log",
        "src/*.js",
        "**/temp",
    ]), encoding='utf-8')
    
    matcher = GitignoreMatcher(tmp_path)
    
    # Test simple glob
    assert matcher.is_ignored(tmp_path / "a.log") is True
    assert matcher.is_ignored(tmp_path / "subdir" / "b.log") is True
    assert matcher.is_ignored(tmp_path / "keep.txt") is False
    
    # Test directory-only pattern
    assert matcher.is_ignored(tmp_path / "build" / "file.txt") is True
    assert matcher.is_ignored(tmp_path / "subdir" / "build" / "file.txt") is True
    
    # Test negation under ignored folder (should still be ignored since parent is ignored)
    assert matcher.is_ignored(tmp_path / "build" / "important.log") is True
    
    # Test root-relative/slash pattern
    assert matcher.is_ignored(tmp_path / "src" / "main.js") is True
    assert matcher.is_ignored(tmp_path / "subdir" / "src" / "main.js") is False
    
    # Test double star anywhere pattern
    assert matcher.is_ignored(tmp_path / "some" / "path" / "temp" / "file.txt") is True
    assert matcher.is_ignored(tmp_path / "temp") is True

def test_gitignore_matcher_negation(tmp_path):
    (tmp_path / ".gitignore").write_text("\n".join([
        "build/*",
        "!build/important.log",
    ]), encoding='utf-8')
    
    matcher = GitignoreMatcher(tmp_path)
    assert matcher.is_ignored(tmp_path / "build" / "file.txt") is True
    assert matcher.is_ignored(tmp_path / "build" / "important.log") is False
