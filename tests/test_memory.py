import os
from pathlib import Path
import pytest
from self_annealing.memory import (
    find_file_in_parents,
    parse_error_log,
    search,
    log_error,
    get_stats,
    list_all
)

def test_find_file_in_parents(tmp_path):
    # Setup temporary directory structure:
    # tmp_path / parent / child / grandchild
    parent = tmp_path / "parent"
    child = parent / "child"
    grandchild = child / "grandchild"
    grandchild.mkdir(parents=True)
    
    # Create target file in parent
    target_file = parent / "test_file.txt"
    target_file.touch()
    
    # Search from grandchild
    found = find_file_in_parents("test_file.txt", start_dir=grandchild)
    assert found is not None
    assert found.resolve() == target_file.resolve()
    
    # Search for non-existent file
    not_found = find_file_in_parents("non_existent.txt", start_dir=grandchild)
    assert not_found is None

def test_parse_error_log_and_stats(tmp_path):
    log_file = tmp_path / "error_log.md"
    
    # Create dummy error log content
    content = """# Error Log

## Error E001
- **Symptom**: [TEMPLATE] MQTT rc=5 auth failure
- **Cause**: Bad username/password
- **Fix**: Check env
- **Context**: mqtt
- **Tokens**: 500

## Error E002
- **Symptom**: Custom symptom
- **Cause**: Custom cause
- **Fix**: Custom fix
- **Context**: deploy
- **Tokens**: 300
"""
    log_file.write_text(content, encoding='utf-8')
    
    entries = parse_error_log(log_file)
    assert len(entries) == 2
    assert entries[0]['id'] == 'E001'
    assert entries[0]['symptom'] == '[TEMPLATE] MQTT rc=5 auth failure'
    assert entries[0]['tokens'] == 500
    
    assert entries[1]['id'] == 'E002'
    assert entries[1]['symptom'] == 'Custom symptom'
    assert entries[1]['tokens'] == 300
    
    # Test list_all (filters [TEMPLATE])
    non_templates = list_all(log_file)
    assert len(non_templates) == 1
    assert non_templates[0]['id'] == 'E002'
    
    # Test get_stats
    stats = get_stats(log_file)
    assert stats['count'] == 2
    assert stats['total_tokens'] == 800
    assert stats['last_modified_str'] != "N/A"

def test_search(tmp_path):
    log_file = tmp_path / "error_log.md"
    content = """# Error Log

## Error E001
- **Symptom**: MQTT rc=5 auth failure
- **Cause**: Bad credentials
- **Fix**: Check config
- **Context**: mqtt
- **Tokens**: 100

## Error E002
- **Symptom**: Database Connection Refused
- **Cause**: Database down
- **Fix**: Restart database
- **Context**: database
- **Tokens**: 200
"""
    log_file.write_text(content, encoding='utf-8')
    
    # HIGH match (exact symptom match)
    results = search(log_file, "MQTT rc=5 auth failure")
    assert len(results) >= 1
    assert results[0][1] == 'HIGH'
    assert results[0][0]['id'] == 'E001'
    
    # MEDIUM match (partial symptom match or context match)
    results_partial = search(log_file, "Connection")
    assert len(results_partial) >= 1
    assert results_partial[0][1] == 'MEDIUM'
    assert results_partial[0][0]['id'] == 'E002'
    
    results_context = search(log_file, "any query", query_context="database")
    assert len(results_context) >= 1
    assert results_context[0][1] == 'MEDIUM'
    assert results_context[0][0]['id'] == 'E002'
    
    # LOW match (word match)
    results_low = search(log_file, "Database Down Refused")
    assert len(results_low) >= 1
    assert results_low[0][1] == 'LOW'
    assert results_low[0][0]['id'] == 'E002'

def test_log_error(tmp_path):
    log_file = tmp_path / "error_log.md"
    
    # Log first error
    log_error(log_file, "E006", "Symptom six", "Cause six", "Fix six", "six-context", 600)
    
    entries = parse_error_log(log_file)
    assert len(entries) == 1
    assert entries[0]['id'] == 'E006'
    assert entries[0]['symptom'] == 'Symptom six'
    assert entries[0]['cause'] == 'Cause six'
    assert entries[0]['fix'] == 'Fix six'
    assert entries[0]['context'] == 'six-context'
    assert entries[0]['tokens'] == 600
    
    # Log second error
    log_error(log_file, "E007", "Symptom seven", "Cause seven", "Fix seven", "seven-context", 700)
    
    entries2 = parse_error_log(log_file)
    assert len(entries2) == 2
    assert entries2[1]['id'] == 'E007'
