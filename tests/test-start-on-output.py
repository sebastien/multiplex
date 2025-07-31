#!/usr/bin/env python3
"""Test cases for start-on-output functionality.

This tests the parsing and behavior of the start-on-output syntax:
- `>A` waits for `A` to output on stdout
- `>2A` waits for `A` to output on stderr
- `>(1A,2A)` waits for `A` to output on both stdout and stderr
- `>(A,B)` waits for `A` or `B` to output on stdout

Format: [KEY][#COLOR][+DELAY…][<REDIRECT…][>START_ON_OUTPUT…][:DEP…][|ACTION…]=COMMAND
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import parse, ParsedCommand, StartOnOutput, StartOnOutputSource, Dependency


def test_no_start_on_output():
	"""Test parsing a command with no start-on-output"""
	result = parse("echo hello")
	expected = ParsedCommand(None, None, 0.0, [], None, None, [], ["echo", "hello"])
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.start_on_output is None
	print("✓ No start-on-output parsing")


def test_simple_stdout_start_on_output():
	"""Test parsing a command with simple stdout start-on-output (>A)"""
	result = parse(">A=echo hello")
	expected = ParsedCommand(None, None, 0.0, [], None, StartOnOutput([StartOnOutputSource("A", 1)]), [], ["echo", "hello"])
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.start_on_output is not None
	assert len(result.start_on_output.sources) == 1
	assert result.start_on_output.sources[0].key == "A"
	assert result.start_on_output.sources[0].stream == 1
	print("✓ Simple stdout start-on-output parsing")


def test_explicit_stdout_start_on_output():
	"""Test parsing a command with explicit stdout start-on-output (>1A)"""
	result = parse(">1A=echo hello")
	expected = ParsedCommand(None, None, 0.0, [], None, StartOnOutput([StartOnOutputSource("A", 1)]), [], ["echo", "hello"])
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.start_on_output.sources[0].stream == 1
	print("✓ Explicit stdout start-on-output parsing")


def test_stderr_start_on_output():
	"""Test parsing a command with stderr start-on-output (>2A)"""
	result = parse(">2A=echo hello")
	expected = ParsedCommand(None, None, 0.0, [], None, StartOnOutput([StartOnOutputSource("A", 2)]), [], ["echo", "hello"])
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.start_on_output.sources[0].stream == 2
	print("✓ Stderr start-on-output parsing")


def test_combined_streams_start_on_output():
	"""Test parsing a command with combined stdout and stderr start-on-output (>(1A,2A))"""
	result = parse(">(1A,2A)=echo hello")
	expected = ParsedCommand(None, None, 0.0, [], None,
		StartOnOutput([StartOnOutputSource("A", 1), StartOnOutputSource("A", 2)]),
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert len(result.start_on_output.sources) == 2
	assert result.start_on_output.sources[0].key == "A"
	assert result.start_on_output.sources[0].stream == 1
	assert result.start_on_output.sources[1].key == "A"
	assert result.start_on_output.sources[1].stream == 2
	print("✓ Combined streams start-on-output parsing")


def test_multiple_processes_start_on_output():
	"""Test parsing a command with multiple processes stdout start-on-output (>(A,B))"""
	result = parse(">(A,B)=echo hello")
	expected = ParsedCommand(None, None, 0.0, [], None,
		StartOnOutput([StartOnOutputSource("A", 1), StartOnOutputSource("B", 1)]),
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert len(result.start_on_output.sources) == 2
	assert result.start_on_output.sources[0].key == "A"
	assert result.start_on_output.sources[0].stream == 1
	assert result.start_on_output.sources[1].key == "B"
	assert result.start_on_output.sources[1].stream == 1
	print("✓ Multiple processes start-on-output parsing")


def test_complex_mixed_start_on_output():
	"""Test parsing a command with complex mixed start-on-output (>(1A,2B))"""
	result = parse(">(1A,2B)=echo hello")
	expected = ParsedCommand(None, None, 0.0, [], None,
		StartOnOutput([StartOnOutputSource("A", 1), StartOnOutputSource("B", 2)]),
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.start_on_output.sources[0].key == "A"
	assert result.start_on_output.sources[0].stream == 1
	assert result.start_on_output.sources[1].key == "B"
	assert result.start_on_output.sources[1].stream == 2
	print("✓ Complex mixed start-on-output parsing")


def test_start_on_output_with_key():
	"""Test parsing a command with start-on-output and key"""
	result = parse("B>A=echo hello")
	expected = ParsedCommand("B", None, 0.0, [], None, StartOnOutput([StartOnOutputSource("A", 1)]), [], ["echo", "hello"])
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.key == "B"
	assert result.start_on_output.sources[0].key == "A"
	print("✓ Start-on-output with key parsing")


def test_start_on_output_with_color():
	"""Test parsing a command with start-on-output and color"""
	result = parse("#red>A=echo hello")
	expected = ParsedCommand(None, "red", 0.0, [], None, StartOnOutput([StartOnOutputSource("A", 1)]), [], ["echo", "hello"])
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.color == "red"
	assert result.start_on_output.sources[0].key == "A"
	print("✓ Start-on-output with color parsing")


def test_start_on_output_with_dependencies():
	"""Test parsing a command with start-on-output and dependencies"""
	result = parse(">A:B=echo hello")
	expected = ParsedCommand(None, None, 0.0, [Dependency("B", False, [])],
		None,
		StartOnOutput([StartOnOutputSource("A", 1)]),
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert len(result.dependencies) == 1
	assert result.dependencies[0].key == "B"
	assert result.start_on_output.sources[0].key == "A"
	print("✓ Start-on-output with dependencies parsing")


def test_start_on_output_with_actions():
	"""Test parsing a command with start-on-output and actions"""
	result = parse(">A|silent=echo hello")
	expected = ParsedCommand(None, None, 0.0, [], None,
		StartOnOutput([StartOnOutputSource("A", 1)]),
		["silent"],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert "silent" in result.actions
	assert result.start_on_output.sources[0].key == "A"
	print("✓ Start-on-output with actions parsing")


def test_full_format_with_start_on_output():
	"""Test parsing full command format with all features including start-on-output"""
	result = parse("worker#blue+1s>(A,2B):C&+1s|silent=python script.py")
	expected = ParsedCommand("worker", "blue", 1.0, [Dependency("C", True, [1.0])],
		None,
		StartOnOutput([StartOnOutputSource("A", 1), StartOnOutputSource("B", 2)]),
		["silent"],
		["python", "script.py"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	assert result.key == "worker"
	assert result.color == "blue"
	assert result.start_delay == 1.0
	assert len(result.dependencies) == 1
	assert result.dependencies[0].key == "C"
	assert result.dependencies[0].wait_for_start == True
	assert len(result.start_on_output.sources) == 2
	assert "silent" in result.actions
	print("✓ Full format with start-on-output parsing")


def test_start_on_output_edge_cases():
	"""Test start-on-output parsing edge cases"""
	# Empty parentheses should return None
	result = parse(">()=echo hello")
	assert result.start_on_output is None, "Empty parentheses should result in no start-on-output"

	# Invalid start-on-output formats should be ignored
	result = parse(">=echo hello")
	assert result.start_on_output is None, "Empty start-on-output should result in no start-on-output"

	# Single letter process names
	result = parse(">X=echo hello")
	assert result.start_on_output.sources[0].key == "X"

	print("✓ Start-on-output edge cases")


def test_parse_start_on_output_function():
	"""Test the parse_start_on_output function directly"""
	from multiplex import parse_start_on_output

	# Test simple cases
	start_on_output = parse_start_on_output(">A")
	assert start_on_output is not None
	assert len(start_on_output.sources) == 1
	assert start_on_output.sources[0].key == "A"
	assert start_on_output.sources[0].stream == 1

	# Test stderr
	start_on_output = parse_start_on_output(">2A")
	assert start_on_output.sources[0].stream == 2

	# Test combined
	start_on_output = parse_start_on_output(">(1A,2A)")
	assert len(start_on_output.sources) == 2

	# Test invalid
	start_on_output = parse_start_on_output("")
	assert start_on_output is None

	start_on_output = parse_start_on_output("A")  # No leading >
	assert start_on_output is None

	print("✓ parse_start_on_output function tests")


if __name__ == "__main__":
	print("Running start-on-output parsing tests...\n")

	test_no_start_on_output()
	test_simple_stdout_start_on_output()
	test_explicit_stdout_start_on_output()
	test_stderr_start_on_output()
	test_combined_streams_start_on_output()
	test_multiple_processes_start_on_output()
	test_complex_mixed_start_on_output()
	test_start_on_output_with_key()
	test_start_on_output_with_color()
	test_start_on_output_with_dependencies()
	test_start_on_output_with_actions()
	test_full_format_with_start_on_output()
	test_start_on_output_edge_cases()
	test_parse_start_on_output_function()

	print("\n✅ All start-on-output parsing tests passed!")