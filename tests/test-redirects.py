#!/usr/bin/env python3
"""Test cases for redirect functionality.

This tests the parsing and behavior of the redirect syntax for stdin redirection:
- `<A…` map stdin to `A` stdout
- `<2A…` map stdin to `A` stderr
- `<(1A,2A)…` map stdin to `A`'s stdout and stderr combined
- `<(A,B)…` map stdin to `A`'s stdout and `B`'s stdout combined

Format: [KEY][#COLOR][<REDIRECT…][:DEP…][|ACTION…]=COMMAND
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import parse, ParsedCommand, Redirect, RedirectSource, Dependency


def test_no_redirect():
	"""Test parsing a command with no redirect"""
	result = parse("echo hello")
	expected = ParsedCommand(None, None, [], None, [], ["echo", "hello"])
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.redirects is None
	print("✓ No redirect parsing")


def test_simple_stdout_redirect():
	"""Test parsing a command with simple stdout redirect (<A)"""
	result = parse("<A=echo hello")
	expected = ParsedCommand(
		None, None, [], Redirect([RedirectSource("A", 1)]), [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.redirects is not None
	assert len(result.redirects.sources) == 1
	assert result.redirects.sources[0].key == "A"
	assert result.redirects.sources[0].stream == 1
	print("✓ Simple stdout redirect parsing")


def test_explicit_stdout_redirect():
	"""Test parsing a command with explicit stdout redirect (<1A)"""
	result = parse("<1A=echo hello")
	expected = ParsedCommand(
		None, None, [], Redirect([RedirectSource("A", 1)]), [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.redirects.sources[0].stream == 1
	print("✓ Explicit stdout redirect parsing")


def test_stderr_redirect():
	"""Test parsing a command with stderr redirect (<2A)"""
	result = parse("<2A=echo hello")
	expected = ParsedCommand(
		None, None, [], Redirect([RedirectSource("A", 2)]), [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.redirects.sources[0].stream == 2
	print("✓ Stderr redirect parsing")


def test_combined_streams_redirect():
	"""Test parsing a command with combined stdout and stderr redirect (<(1A,2A))"""
	result = parse("<(1A,2A)=echo hello")
	expected = ParsedCommand(
		None,
		None,
		[],
		Redirect([RedirectSource("A", 1), RedirectSource("A", 2)]),
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert len(result.redirects.sources) == 2
	assert result.redirects.sources[0].key == "A"
	assert result.redirects.sources[0].stream == 1
	assert result.redirects.sources[1].key == "A"
	assert result.redirects.sources[1].stream == 2
	print("✓ Combined streams redirect parsing")


def test_multiple_processes_redirect():
	"""Test parsing a command with multiple processes stdout redirect (<(A,B))"""
	result = parse("<(A,B)=echo hello")
	expected = ParsedCommand(
		None,
		None,
		[],
		Redirect([RedirectSource("A", 1), RedirectSource("B", 1)]),
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert len(result.redirects.sources) == 2
	assert result.redirects.sources[0].key == "A"
	assert result.redirects.sources[0].stream == 1
	assert result.redirects.sources[1].key == "B"
	assert result.redirects.sources[1].stream == 1
	print("✓ Multiple processes redirect parsing")


def test_complex_mixed_redirect():
	"""Test parsing a command with complex mixed redirect (<(1A,2B))"""
	result = parse("<(1A,2B)=echo hello")
	expected = ParsedCommand(
		None,
		None,
		[],
		Redirect([RedirectSource("A", 1), RedirectSource("B", 2)]),
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.redirects.sources[0].key == "A"
	assert result.redirects.sources[0].stream == 1
	assert result.redirects.sources[1].key == "B"
	assert result.redirects.sources[1].stream == 2
	print("✓ Complex mixed redirect parsing")


def test_redirect_with_key():
	"""Test parsing a command with redirect and key"""
	result = parse("B<A=echo hello")
	expected = ParsedCommand(
		"B", None, [], Redirect([RedirectSource("A", 1)]), [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.key == "B"
	assert result.redirects.sources[0].key == "A"
	print("✓ Redirect with key parsing")


def test_redirect_with_color():
	"""Test parsing a command with redirect and color"""
	result = parse("#red<A=echo hello")
	expected = ParsedCommand(
		None, "red", [], Redirect([RedirectSource("A", 1)]), [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.color == "red"
	assert result.redirects.sources[0].key == "A"
	print("✓ Redirect with color parsing")


def test_redirect_with_dependencies():
	"""Test parsing a command with redirect and dependencies"""
	result = parse("<A:B=echo hello")
	expected = ParsedCommand(
		None,
		None,
		[Dependency("B", False, [])],
		Redirect([RedirectSource("A", 1)]),
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert len(result.dependencies) == 1
	assert result.dependencies[0].key == "B"
	assert result.redirects.sources[0].key == "A"
	print("✓ Redirect with dependencies parsing")


def test_redirect_with_actions():
	"""Test parsing a command with redirect and actions"""
	result = parse("<A|silent=echo hello")
	expected = ParsedCommand(
		None,
		None,
		[],
		Redirect([RedirectSource("A", 1)]),
		["silent"],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert "silent" in result.actions
	assert result.redirects.sources[0].key == "A"
	print("✓ Redirect with actions parsing")


def test_full_format_with_redirect():
	"""Test parsing full command format with all features including redirect"""
	result = parse("worker#blue<(A,2B):C&+1s|silent=python script.py")
	expected = ParsedCommand(
		"worker",
		"blue",
		[Dependency("C", True, [1.0])],
		Redirect([RedirectSource("A", 1), RedirectSource("B", 2)]),
		["silent"],
		["python", "script.py"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.key == "worker"
	assert result.color == "blue"
	assert len(result.dependencies) == 1
	assert result.dependencies[0].key == "C"
	assert result.dependencies[0].wait_for_start == True
	assert len(result.redirects.sources) == 2
	assert "silent" in result.actions
	print("✓ Full format with redirect parsing")


def test_redirect_edge_cases():
	"""Test redirect parsing edge cases"""
	# Empty parentheses should return None
	result = parse("<()=echo hello")
	assert result.redirects is None, "Empty parentheses should result in no redirect"

	# Invalid redirect formats should be ignored
	result = parse("<=echo hello")
	assert result.redirects is None, "Empty redirect should result in no redirect"

	# Single letter process names
	result = parse("<X=echo hello")
	assert result.redirects.sources[0].key == "X"

	print("✓ Redirect edge cases")


def test_parse_redirects_function():
	"""Test the parse_redirects function directly"""
	from multiplex import parse_redirects

	# Test simple cases
	redirect = parse_redirects("<A")
	assert redirect is not None
	assert len(redirect.sources) == 1
	assert redirect.sources[0].key == "A"
	assert redirect.sources[0].stream == 1

	# Test stderr
	redirect = parse_redirects("<2A")
	assert redirect.sources[0].stream == 2

	# Test combined
	redirect = parse_redirects("<(1A,2A)")
	assert len(redirect.sources) == 2

	# Test invalid
	redirect = parse_redirects("")
	assert redirect is None

	redirect = parse_redirects("A")  # No leading <
	assert redirect is None

	print("✓ parse_redirects function tests")


if __name__ == "__main__":
	print("Running redirect parsing tests...\n")

	test_no_redirect()
	test_simple_stdout_redirect()
	test_explicit_stdout_redirect()
	test_stderr_redirect()
	test_combined_streams_redirect()
	test_multiple_processes_redirect()
	test_complex_mixed_redirect()
	test_redirect_with_key()
	test_redirect_with_color()
	test_redirect_with_dependencies()
	test_redirect_with_actions()
	test_full_format_with_redirect()
	test_redirect_edge_cases()
	test_parse_redirects_function()

	print("\n✅ All redirect parsing tests passed!")
