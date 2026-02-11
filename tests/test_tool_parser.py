import pytest
from orket.services.tool_parser import ToolParser

def test_parse_clean_json():
    text = '{"tool": "read_file", "args": {"path": "test.txt"}}'
    results = ToolParser.parse(text)
    assert len(results) == 1
    assert results[0]["tool"] == "read_file"
    assert results[0]["args"]["path"] == "test.txt"

def test_parse_with_noise():
    text = """
    I will read the file now.
    {"tool": "read_file", "args": {"path": "test.txt"}}
    Hope this helps!
    """
    results = ToolParser.parse(text)
    assert len(results) == 1
    assert results[0]["tool"] == "read_file"

def test_parse_openai_format():
    text = '{"name": "write_file", "arguments": {"path": "out.py", "content": "print(1)"}}'
    results = ToolParser.parse(text)
    assert len(results) == 1
    assert results[0]["tool"] == "write_file"
    assert results[0]["args"]["path"] == "out.py"

def test_parse_openai_string_arguments():
    text = '{"name": "write_file", "arguments": "{\\"path\\": \\"out.py\\"}"}'
    results = ToolParser.parse(text)
    assert len(results) == 1
    assert results[0]["tool"] == "write_file"
    assert results[0]["args"]["path"] == "out.py"

def test_parse_function_wrapper():
    text = '{"function": {"name": "list_directory", "arguments": {"path": "."}}}'
    results = ToolParser.parse(text)
    assert len(results) == 1
    assert results[0]["tool"] == "list_directory"

def test_parse_multiple_tools():
    text = """
    {"tool": "tool1", "args": {}}
    Some text
    {"tool": "tool2", "args": {}}
    """
    results = ToolParser.parse(text)
    assert len(results) == 2
    assert results[0]["tool"] == "tool1"
    assert results[1]["tool"] == "tool2"

def test_parse_nested_json():
    text = '{"tool": "complex", "args": {"data": {"nested": [1, 2, 3]}}}'
    results = ToolParser.parse(text)
    assert len(results) == 1
    assert results[0]["args"]["data"]["nested"] == [1, 2, 3]

def test_parse_malformed_json_recovery():
    text = """
    Invalid: {"tool": "bad", "args": { ... }}
    Valid: {"tool": "good", "args": {"x": 1}}
    """
    results = ToolParser.parse(text)
    assert len(results) == 1
    assert results[0]["tool"] == "good"

def test_parse_legacy_dsl_fallback():
    text = """TOOL: write_file
PATH: script.py
CONTENT: print("hello")"""
    results = ToolParser.parse(text)
    assert len(results) == 1
    assert results[0]["tool"] == "write_file"
    assert results[0]["args"]["path"] == "script.py"
    assert results[0]["args"]["content"] == 'print("hello")'

def test_parse_legacy_dsl_shorthand():
    text = """[create_issue]
PATH: task.txt
CONTENT: New task"""
    results = ToolParser.parse(text)
    assert len(results) == 1
    assert results[0]["tool"] == "create_issue"
    assert results[0]["args"]["path"] == "task.txt"
