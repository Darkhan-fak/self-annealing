import os
from pathlib import Path
import pytest
from self_annealing.doc_search import search_docs

def test_search_docs_basic(tmp_path):
    # Setup temporary directory structure:
    # tmp_path / doc1.md
    # tmp_path / doc2.md
    # tmp_path / sub / doc3.md
    
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("This is a simple document about self-annealing project.", encoding='utf-8')
    
    doc2 = tmp_path / "doc2.md"
    doc2.write_text("Documentation search is awesome. Let's search documents.", encoding='utf-8')
    
    sub = tmp_path / "sub"
    sub.mkdir()
    doc3 = sub / "doc3.md"
    doc3.write_text("Self-annealing is a project that helps in AI-assisted development.", encoding='utf-8')
    
    # Search for "self-annealing"
    results = search_docs(str(tmp_path), "self-annealing")
    assert len(results) == 2
    
    # The documents that matched are doc1.md and sub/doc3.md
    # Rank check:
    # "self-annealing" in doc1.md -> count: 1
    # "self-annealing" in sub/doc3.md -> count: 1
    # Sorting by score (both 1), then filename alphabetically: "doc1.md" < "sub/doc3.md"
    assert results[0]['filename'] == "doc1.md"
    assert results[0]['score'] == 1
    assert "self-annealing" in results[0]['snippet'].lower()
    
    assert results[1]['filename'] == "sub/doc3.md"
    assert results[1]['score'] == 1
    assert "self-annealing" in results[1]['snippet'].lower()

def test_search_docs_ranking(tmp_path):
    # Setup files with different numbers of occurrences
    doc_low = tmp_path / "low.md"
    doc_low.write_text("keyword once", encoding='utf-8')
    
    doc_high = tmp_path / "high.md"
    doc_high.write_text("keyword keyword keyword", encoding='utf-8')
    
    doc_med = tmp_path / "medium.md"
    doc_med.write_text("keyword keyword", encoding='utf-8')
    
    results = search_docs(str(tmp_path), "keyword")
    assert len(results) == 3
    assert results[0]['filename'] == "high.md"
    assert results[0]['score'] == 3
    
    assert results[1]['filename'] == "medium.md"
    assert results[1]['score'] == 2
    
    assert results[2]['filename'] == "low.md"
    assert results[2]['score'] == 1

def test_search_docs_case_insensitivity(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("KeYwOrD once. KEYWORD twice.", encoding='utf-8')
    
    results = search_docs(str(tmp_path), "keyword")
    assert len(results) == 1
    assert results[0]['score'] == 2
    assert "keyword" in results[0]['snippet'].lower()

def test_search_docs_excludes(tmp_path):
    # File in normal dir
    doc_ok = tmp_path / "doc_ok.md"
    doc_ok.write_text("my keyword", encoding='utf-8')
    
    # Files in excluded dirs
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "hidden.md").write_text("my keyword", encoding='utf-8')
    
    node_dir = tmp_path / "node_modules"
    node_dir.mkdir()
    (node_dir / "npm.md").write_text("my keyword", encoding='utf-8')
    
    egg_dir = tmp_path / "project.egg-info"
    egg_dir.mkdir()
    (egg_dir / "egg.md").write_text("my keyword", encoding='utf-8')
    
    results = search_docs(str(tmp_path), "keyword")
    assert len(results) == 1
    assert results[0]['filename'] == "doc_ok.md"

def test_search_docs_extensions(tmp_path):
    doc_md = tmp_path / "doc.md"
    doc_md.write_text("target word", encoding='utf-8')
    
    doc_txt = tmp_path / "doc.txt"
    doc_txt.write_text("target word", encoding='utf-8')
    
    doc_py = tmp_path / "doc.py"
    doc_py.write_text("target word", encoding='utf-8')
    
    results = search_docs(str(tmp_path), "target")
    assert len(results) == 1
    assert results[0]['filename'] == "doc.md"

def test_search_docs_empty_and_punctuation(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("Hello World!", encoding='utf-8')
    
    # Empty query
    assert search_docs(str(tmp_path), "") == []
    assert search_docs(str(tmp_path), "   ") == []
    
    # Query with only punctuation
    assert search_docs(str(tmp_path), "...,") == []

def test_search_docs_nonexistent_dir():
    assert search_docs("non_existent_directory_xyz", "keyword") == []

def test_search_docs_snippet_boundaries(tmp_path):
    doc = tmp_path / "doc.md"
    long_prefix = "A" * 100
    long_suffix = "B" * 100
    doc.write_text(f"{long_prefix}target{long_suffix}", encoding='utf-8')
    
    results = search_docs(str(tmp_path), "target")
    assert len(results) == 1
    snippet = results[0]['snippet']
    assert "target" in snippet
    assert snippet.startswith("...")
    assert snippet.endswith("...")
    # snippet length should be around 60 chars before and 60 chars after + len("target") = 126
    # including "..." it should be around 132 chars
    assert len(snippet) < 140
