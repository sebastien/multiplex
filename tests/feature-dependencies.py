#!/usr/bin/env python3
"""Test cases for the upgraded command format with dependencies.

This module tests the parsing of the new command format:
[KEY][#COLOR][:DEP…][|ACTION…]=COMMAND

Where DEP is: [KEY][&][+DELAY…]
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import parse, ParsedCommand, Dependency, parse_dependencies


def test_basic_command_no_dependencies():
	"""Test parsing a basic command without dependencies"""
	result = parse("echo hello")
	expected = ParsedCommand(None, None, 0.0, [], None, [], ["echo", "hello"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Basic command parsing (no dependencies)")


def test_named_command_no_dependencies():
	"""Test parsing a named command without dependencies"""
	result = parse("A=echo hello")
	expected = ParsedCommand("A", None, 0.0, [], None, [], ["echo", "hello"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Named command parsing (no dependencies)")


def test_simple_dependency():
	"""Test parsing a command with a simple dependency"""
	result = parse(":A=echo hello")
	expected = ParsedCommand(None, None, 0.0, [Dependency("A", False, [])], None, [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Simple dependency parsing")


def test_dependency_with_start_indicator():
	"""Test parsing a dependency with & (wait for start)"""
	result = parse(":A&=echo hello")
	expected = ParsedCommand(None, None, 0.0, [Dependency("A", True, [])], None, [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency with start indicator parsing")


def test_dependency_with_delay():
	"""Test parsing a dependency with delay"""
	result = parse(":A+1s=echo hello")
	expected = ParsedCommand(None, None, 0.0, [Dependency("A", False, [1.0])], None, [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency with delay parsing")


def test_dependency_with_start_and_delay():
	"""Test parsing a dependency with & and delay"""
	result = parse(":A&+500ms=echo hello")
	expected = ParsedCommand(None, None, 0.0, [Dependency("A", True, [0.5])], None, [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency with start indicator and delay parsing")


def test_multiple_delays_on_dependency():
	"""Test parsing a dependency with multiple delays"""
	result = parse(":A+1s+500ms=echo hello")
	expected = ParsedCommand(None, None, 0.0, [Dependency("A", False, [1.0, 0.5])], None, [], ["echo", "hello"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Multiple delays on dependency parsing")


def test_multiple_dependencies():
	"""Test parsing multiple dependencies"""
	result = parse(":A:B&=echo hello")
	expected = ParsedCommand(None, None, 0.0, [Dependency("A", False, []), Dependency("B", True, [])],
		None,
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Multiple dependencies parsing")


def test_complex_dependencies():
	"""Test parsing complex dependencies with various combinations"""
	result = parse(":A+1s:B&+500ms:C+2m=echo hello")
	expected = ParsedCommand(None, None, 0.0, [
			Dependency("A", False, [1.0]),
			Dependency("B", True, [0.5]),
			Dependency("C", False, [120.0]),
		],
		None,
		[],
		["echo", "hello"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Complex dependencies parsing")


def test_full_command_format():
	"""Test parsing full command format with key, color, dependencies, and actions"""
	result = parse("worker#blue:A+1s:B&|silent=python script.py")
	expected = ParsedCommand("worker", "blue", 0.0, [Dependency("A", False, [1.0]), Dependency("B", True, [])],
		None,
		["silent"],
		["python", "script.py"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Full command format parsing")


def test_dependencies_with_actions():
	"""Test parsing dependencies combined with actions"""
	result = parse(":DB:API&+2s|silent|end=echo done")
	expected = ParsedCommand(None, None, 0.0, [Dependency("DB", False, []), Dependency("API", True, [2.0])],
		None,
		["silent", "end"],
		["echo", "done"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependencies with actions parsing")


def test_parse_dependencies_function():
	"""Test the parse_dependencies function directly"""
	# Single dependency
	deps = parse_dependencies(":A")
	assert len(deps) == 1
	assert deps[0] == Dependency("A", False, [])

	# Dependency with start indicator
	deps = parse_dependencies(":A&")
	assert len(deps) == 1
	assert deps[0] == Dependency("A", True, [])

	# Dependency with delay
	deps = parse_dependencies(":A+1s")
	assert len(deps) == 1
	assert deps[0] == Dependency("A", False, [1.0])

	# Dependency with start and delay
	deps = parse_dependencies(":A&+500ms")
	assert len(deps) == 1
	assert deps[0] == Dependency("A", True, [0.5])

	# Multiple dependencies
	deps = parse_dependencies(":A:B&:C+2s")
	assert len(deps) == 3
	assert deps[0] == Dependency("A", False, [])
	assert deps[1] == Dependency("B", True, [])
	assert deps[2] == Dependency("C", False, [2.0])

	# Complex delays
	deps = parse_dependencies(":A+1s+500ms")
	assert len(deps) == 1
	assert deps[0] == Dependency("A", False, [1.0, 0.5])

	print("✓ parse_dependencies function tests")


def test_backward_compatibility():
	"""Test that commands without dependencies still work"""
	# Basic commands
	result = parse("echo test")
	expected = ParsedCommand(None, None, 0.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"

	# Named commands
	result = parse("A=echo test")
	expected = ParsedCommand("A", None, 0.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"

	# Commands with color
	result = parse("A#red=echo test")
	expected = ParsedCommand("A", "red", 0.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"

	# Commands with actions
	result = parse("A#red|silent=echo test")
	expected = ParsedCommand("A", "red", 0.0, [], None, ["silent"], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"

	print("✓ Backward compatibility")


def test_edge_cases():
	"""Test edge cases and error conditions"""
	# Empty dependency string
	deps = parse_dependencies("")
	assert deps == []

	# Malformed dependency strings
	deps = parse_dependencies(":")
	assert deps == []

	deps = parse_dependencies("::")
	assert deps == []

	# Dependencies with invalid delays (should be skipped)
	deps = parse_dependencies(":A+invalid")
	assert len(deps) == 1
	assert deps[0] == Dependency("A", False, [])

	print("✓ Edge cases")


def run_tests():
	"""Run all dependency feature tests"""
	print("Running upgraded command format tests...\n")

	test_basic_command_no_dependencies()
	test_named_command_no_dependencies()
	test_simple_dependency()
	test_dependency_with_start_indicator()
	test_dependency_with_delay()
	test_dependency_with_start_and_delay()
	test_multiple_delays_on_dependency()
	test_multiple_dependencies()
	test_complex_dependencies()
	test_full_command_format()
	test_dependencies_with_actions()
	test_parse_dependencies_function()
	test_backward_compatibility()
	test_edge_cases()

	print("\n✅ All upgraded command format tests passed!")


if __name__ == "__main__":
	run_tests()
