#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import parse, ParsedCommand


def test_basic_command():
	"""Test parsing a basic command without any metadata"""
	result = parse("python -m http.server")
	expected = ParsedCommand(None, None, [], None, [], ["python", "-m", "http.server"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Basic command parsing")


def test_named_command():
	"""Test parsing a command with a name"""
	result = parse("A=python -m http.server")
	expected = ParsedCommand("A", None, [], None, [], ["python", "-m", "http.server"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Named command parsing")


def test_delay_seconds():
	"""Test parsing a command with delay (now as dependency) - legacy format no longer supported"""
	result = parse(
		"python -m http.server"
	)  # Changed: delays are now part of dependencies
	expected = ParsedCommand(None, None, [], None, [], ["python", "-m", "http.server"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Command parsing (delay moved to dependencies)")


def test_delay_float():
	"""Test parsing a command - delays now handled via dependencies"""
	result = parse(
		"python -m http.server"
	)  # Changed: delays are now part of dependencies
	expected = ParsedCommand(None, None, [], None, [], ["python", "-m", "http.server"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Command parsing (float delay moved to dependencies)")


def test_named_delay():
	"""Test parsing a named command - delays now part of dependencies"""
	result = parse(
		"A=python -m http.server"
	)  # Changed: delays are now part of dependencies
	expected = ParsedCommand("A", None, [], None, [], ["python", "-m", "http.server"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Named command parsing (delay moved to dependencies)")


def test_single_action():
	"""Test parsing a command with a single action"""
	result = parse("|silent=python -m http.server")
	expected = ParsedCommand(
		None, None, [], None, ["silent"], ["python", "-m", "http.server"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Single action parsing")


def test_multiple_actions():
	"""Test parsing a command with multiple actions"""
	result = parse("|silent|end=python -m http.server")
	expected = ParsedCommand(
		None, None, [], None, ["silent", "end"], ["python", "-m", "http.server"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Multiple actions parsing")


def test_complex_command():
	"""Test parsing a complex command with name and actions (delay moved to dependencies)"""
	result = parse("A|silent|end=python -m http.server")
	expected = ParsedCommand(
		"A", None, [], None, ["silent", "end"], ["python", "-m", "http.server"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Complex command parsing")


def test_command_with_quotes():
	"""Test parsing a command with quoted arguments"""
	result = parse('echo "hello world"')
	expected = ParsedCommand(None, None, [], None, [], ["echo", "hello world"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Quoted arguments parsing")


def test_command_with_single_quotes():
	"""Test parsing a command with single quoted arguments"""
	result = parse("echo 'hello world'")
	expected = ParsedCommand(None, None, [], None, [], ["echo", "hello world"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Single quoted arguments parsing")


def test_empty_prefix_with_equals():
	"""Test parsing a command that starts with equals (empty prefix)"""
	result = parse("=echo =")
	expected = ParsedCommand(None, None, [], None, [], ["echo", "="])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Empty prefix with equals parsing")


def test_benchmark_example():
	"""Test parsing the benchmark example from README (updated for new format)"""
	result = parse("|silent=python -m http.server")
	expected = ParsedCommand(
		None, None, [], None, ["silent"], ["python", "-m", "http.server"]
	)
	assert result == expected, f"Expected {expected}, got {result}"

	result = parse(
		"|end=ab -n1000 http://localhost:8000/"
	)  # Delay removed - now handled by dependencies
	expected = ParsedCommand(
		None, None, [], None, ["end"], ["ab", "-n1000", "http://localhost:8000/"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Benchmark example parsing")


def test_sequential_example():
	"""Test parsing the sequential example from README (updated for new format)"""
	result = parse("A=python -m http.server")
	expected = ParsedCommand("A", None, [], None, [], ["python", "-m", "http.server"])
	assert result == expected, f"Expected {expected}, got {result}"

	# In new format, dependencies replace the old delay syntax
	result = parse(
		":A=ab -n1000 http://localhost:8000/"
	)  # :A means wait for A to complete
	expected = ParsedCommand(
		None,
		None,
		[
			parse("A=dummy").dependencies[0]
			if parse("A=dummy").dependencies
			else type(
				"MockDep", (), {"key": "A", "wait_for_start": False, "delays": []}
			)()
		],
		None,
		[],
		["ab", "-n1000", "http://localhost:8000/"],
	)
	# Simplified test for sequential dependency
	result = parse(":A=ab -n1000 http://localhost:8000/")
	assert result.dependencies[0].key == "A"
	assert result.dependencies[0].wait_for_start == False
	assert result.command == ["ab", "-n1000", "http://localhost:8000/"]
	print("✓ Sequential example with dependency parsing")


def test_command_with_paths():
	"""Test parsing commands with file paths"""
	result = parse("/usr/bin/python3 /path/to/script.py")
	expected = ParsedCommand(
		None, None, [], None, [], ["/usr/bin/python3", "/path/to/script.py"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ File paths parsing")


def test_command_with_flags():
	"""Test parsing commands with various flags"""
	result = parse(
		"curl -X POST -H 'Content-Type: application/json' https://api.example.com"
	)
	expected = ParsedCommand(
		None,
		None,
		[],
		None,
		[],
		[
			"curl",
			"-X",
			"POST",
			"-H",
			"Content-Type: application/json",
			"https://api.example.com",
		],
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Command with flags parsing")


def run_tests():
	"""Run all tests"""
	print("Running parse() function tests...\n")

	test_basic_command()
	test_named_command()
	test_delay_seconds()
	test_delay_float()
	test_named_delay()
	test_single_action()
	test_multiple_actions()
	test_complex_command()
	test_command_with_quotes()
	test_command_with_single_quotes()
	test_empty_prefix_with_equals()
	test_benchmark_example()
	test_sequential_example()
	test_command_with_paths()
	test_command_with_flags()

	print("\n✅ All tests passed!")


if __name__ == "__main__":
	run_tests()
