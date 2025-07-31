#!/usr/bin/env python3
"""Test cases for delay suffixes within dependencies.

With the new command format, delays are now part of dependencies.
This module tests delay parsing within the dependency context.

Format: [KEY][#COLOR][:DEP…][|ACTION…]=COMMAND
Where DEP is: [KEY][&][+DELAY…]
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import parse, ParsedCommand, Dependency, parse_delay


def test_delay_parsing_compatibility():
	"""Test that the parse_delay function still works correctly"""
	# Basic suffixes
	assert parse_delay("500ms") == 0.5
	assert parse_delay("5s") == 5.0
	assert parse_delay("2m") == 120.0
	assert parse_delay("1m30s") == 90.0

	# Complex combinations
	assert parse_delay("1m1s1ms") == 61.001
	assert parse_delay("2s500ms") == 2.5
	assert parse_delay("1m500ms") == 60.5

	# Plain numbers
	assert parse_delay("5") == 5.0
	assert parse_delay("1.0") == 1.0

	print("✓ parse_delay function compatibility")


def test_dependency_with_millisecond_delay():
	"""Test dependency with millisecond delay"""
	result = parse(":A+500ms=echo test")
	expected = ParsedCommand(
		None, None, [Dependency("A", False, [0.5])], None, [], ["echo", "test"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency with millisecond delay")


def test_dependency_with_second_delay():
	"""Test dependency with second delay"""
	result = parse(":A+5s=echo test")
	expected = ParsedCommand(
		None, None, [Dependency("A", False, [5.0])], None, [], ["echo", "test"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency with second delay")


def test_dependency_with_minute_delay():
	"""Test dependency with minute delay"""
	result = parse(":A+2m=echo test")
	expected = ParsedCommand(
		None, None, [Dependency("A", False, [120.0])], None, [], ["echo", "test"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency with minute delay")


def test_dependency_with_complex_delay():
	"""Test dependency with complex delay combination"""
	result = parse(":A+1m30s=echo test")
	expected = ParsedCommand(
		None, None, [Dependency("A", False, [90.0])], None, [], ["echo", "test"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency with complex delay combination")


def test_dependency_with_multiple_delays():
	"""Test dependency with multiple separate delays"""
	result = parse(":A+1s+500ms=echo test")
	expected = ParsedCommand(
		None, None, [Dependency("A", False, [1.0, 0.5])], None, [], ["echo", "test"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency with multiple delays")


def test_dependency_with_maximum_complexity():
	"""Test dependency with maximum complexity timing"""
	result = parse(":A+2m30s750ms=echo test")
	expected = ParsedCommand(
		None, None, [Dependency("A", False, [150.75])], None, [], ["echo", "test"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency with maximum complexity timing")


def test_start_dependency_with_delays():
	"""Test start dependency with delays"""
	result = parse(":A&+1s+500ms=echo test")
	expected = ParsedCommand(
		None, None, [Dependency("A", True, [1.0, 0.5])], None, [], ["echo", "test"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Start dependency with delays")


def test_multiple_dependencies_with_delays():
	"""Test multiple dependencies each with their own delays"""
	result = parse(":A+1s:B&+500ms:C+2m=echo test")
	expected = ParsedCommand(
		None,
		None,
		[
			Dependency("A", False, [1.0]),
			Dependency("B", True, [0.5]),
			Dependency("C", False, [120.0]),
		],
		None,
		[],
		["echo", "test"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Multiple dependencies with delays")


def test_dependency_delays_with_full_format():
	"""Test dependency delays with full command format"""
	result = parse("worker#blue:A+1s:B&+500ms|silent=python script.py")
	expected = ParsedCommand(
		"worker",
		"blue",
		[Dependency("A", False, [1.0]), Dependency("B", True, [0.5])],
		None,
		["silent"],
		["python", "script.py"],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Dependency delays with full command format")


def test_backward_compatibility_note():
	"""Note about backward compatibility changes"""
	# The old delay format (+1s=command) is no longer supported
	# Delays are now part of dependencies (:A+1s=command)

	# Old format would have been: "+1s=echo test"
	# New format is: ":PROCESS+1s=echo test" (wait for PROCESS, then delay 1s)

	# For immediate delays without dependencies, you would need a dummy dependency
	# or handle it differently in the application logic

	print("✓ Backward compatibility note: delays moved to dependencies")


def run_tests():
	"""Run all delay suffix tests in dependency context"""
	print("Running delay suffixes in dependencies tests...\n")

	test_delay_parsing_compatibility()
	test_dependency_with_millisecond_delay()
	test_dependency_with_second_delay()
	test_dependency_with_minute_delay()
	test_dependency_with_complex_delay()
	test_dependency_with_multiple_delays()
	test_dependency_with_maximum_complexity()
	test_start_dependency_with_delays()
	test_multiple_dependencies_with_delays()
	test_dependency_delays_with_full_format()
	test_backward_compatibility_note()

	print("\n✅ All delay suffix in dependencies tests passed!")


if __name__ == "__main__":
	run_tests()
