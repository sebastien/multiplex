#!/usr/bin/env python3
"""Test cases for delay suffix feature.

This module tests the parsing of delay suffixes including:
- +1ms for milliseconds
- +1s for seconds
- +1m for minutes
- +1m10s for minutes/seconds combinations
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import parse, ParsedCommand, parse_delay


def test_millisecond_suffix():
	"""Test parsing delay with millisecond suffix"""
	result = parse("+500ms=echo test")
	expected = ParsedCommand(None, None, 0.5, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Millisecond suffix parsing")


def test_second_suffix():
	"""Test parsing delay with second suffix"""
	result = parse("+5s=echo test")
	expected = ParsedCommand(None, None, 5.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Second suffix parsing")


def test_minute_suffix():
	"""Test parsing delay with minute suffix"""
	result = parse("+2m=echo test")
	expected = ParsedCommand(None, None, 120.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Minute suffix parsing")


def test_minute_second_combination():
	"""Test parsing delay with minute+second combination"""
	result = parse("+1m30s=echo test")
	expected = ParsedCommand(None, None, 90.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Minute+second combination parsing")


def test_complex_minute_second_combination():
	"""Test parsing delay with complex minute+second combination"""
	result = parse("+2m15s=echo test")
	expected = ParsedCommand(None, None, 135.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Complex minute+second combination parsing")


def test_float_milliseconds():
	"""Test parsing delay with float milliseconds"""
	result = parse("+1500ms=echo test")
	expected = ParsedCommand(None, None, 1.5, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Float milliseconds parsing")


def test_float_seconds():
	"""Test parsing delay with float seconds"""
	result = parse("+2.5s=echo test")
	expected = ParsedCommand(None, None, 2.5, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Float seconds parsing")


def test_float_minutes():
	"""Test parsing delay with float minutes"""
	result = parse("+1.5m=echo test")
	expected = ParsedCommand(None, None, 90.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Float minutes parsing")


def test_named_delay_with_key():
	"""Test named delay with key still works"""
	result = parse("A+2s=echo test")
	expected = ParsedCommand("A", None, 2.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Named delay with key parsing")


def test_suffix_with_actions():
	"""Test delay suffix with actions"""
	result = parse("+1m|silent=echo test")
	expected = ParsedCommand(None, None, 60.0, [], None, ["silent"], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Delay suffix with actions parsing")


def test_complex_combination():
	"""Test complex combination with key, color, delay suffix, and actions"""
	result = parse("worker#blue+30s|silent=python script.py")
	expected = ParsedCommand(
		"worker", "blue", 30.0, [], None, ["silent"], ["python", "script.py"]
	)
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Complex combination parsing")


def test_complex_combinations():
	"""Test complex delay combinations with all units"""
	result = parse("+1m1s1ms=echo test")
	expected = ParsedCommand(None, None, 61.001, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Complex 1m1s1ms combination parsing")


def test_milliseconds_only():
	"""Test pure millisecond delays"""
	result = parse("+250ms=echo test")
	expected = ParsedCommand(None, None, 0.25, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Pure milliseconds parsing")


def test_plain_integer():
	"""Test plain integer without decimal"""
	result = parse("+5=echo test")
	expected = ParsedCommand(None, None, 5.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Plain integer parsing")


def test_plain_float_with_zero():
	"""Test plain float with explicit zero decimal"""
	result = parse("+1.0=echo test")
	expected = ParsedCommand(None, None, 1.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Plain float with .0 parsing")


def test_seconds_and_milliseconds():
	"""Test seconds combined with milliseconds"""
	result = parse("+2s500ms=echo test")
	expected = ParsedCommand(None, None, 2.5, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Seconds+milliseconds combination parsing")


def test_minutes_and_milliseconds():
	"""Test minutes combined with milliseconds"""
	result = parse("+1m500ms=echo test")
	expected = ParsedCommand(None, None, 60.5, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ Minutes+milliseconds combination parsing")


def test_all_units_maximum():
	"""Test maximum complexity with all units"""
	result = parse("+2m30s750ms=echo test")
	expected = ParsedCommand(None, None, 150.75, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"
	print("✓ All units maximum complexity parsing")


def test_parse_delay_function():
	"""Test the parse_delay function directly with all supported formats"""
	# Basic suffixes
	assert parse_delay("500ms") == 0.5
	assert parse_delay("5s") == 5.0
	assert parse_delay("2m") == 120.0
	assert parse_delay("1m30s") == 90.0
	assert parse_delay("2m15s") == 135.0

	# Plain numbers
	assert parse_delay("5") == 5.0
	assert parse_delay("1.5") == 1.5
	assert parse_delay("1.0") == 1.0

	# Complex combinations
	assert parse_delay("1m1s1ms") == 61.001
	assert parse_delay("2s500ms") == 2.5
	assert parse_delay("1m500ms") == 60.5
	assert parse_delay("2m30s750ms") == 150.75

	# Named delays
	assert parse_delay("A") == "A"
	assert parse_delay("server") == "server"

	print("✓ parse_delay function tests (extended)")


def test_start_delay_validation():
	"""Test that existing delay formats still work"""
	# Plain numeric delays should still work
	result = parse("+5=echo test")
	expected = ParsedCommand(None, None, 5.0, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"

	# Float delays should still work
	result = parse("+1.5=echo test")
	expected = ParsedCommand(None, None, 1.5, [], None, [], ["echo", "test"])
	assert result == expected, f"Expected {expected}, got {result}"

	# Named delays for start_delay should raise an error
	try:
		result = parse("+A=echo test")
		assert False, "Should have raised SyntaxError for named start delay"
	except SyntaxError:
		pass  # This is expected

	print("✓ Start delay validation")


def run_tests():
	"""Run all delay suffix tests"""
	print("Running delay suffix feature tests...\n")

	test_millisecond_suffix()
	test_second_suffix()
	test_minute_suffix()
	test_minute_second_combination()
	test_complex_minute_second_combination()
	test_float_milliseconds()
	test_float_seconds()
	test_float_minutes()
	test_named_delay_with_key()
	test_suffix_with_actions()
	test_complex_combination()

	# New comprehensive tests
	test_complex_combinations()
	test_milliseconds_only()
	test_plain_integer()
	test_plain_float_with_zero()
	test_seconds_and_milliseconds()
	test_minutes_and_milliseconds()
	test_all_units_maximum()

	test_parse_delay_function()
	test_start_delay_validation()

	print("\n✅ All delay suffix tests passed!")


if __name__ == "__main__":
	run_tests()
