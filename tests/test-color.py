#!/usr/bin/env python3
"""Test cases for color functionality in multiplex."""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src directory to path so we can import multiplex
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "py"))

from multiplex import parse, ParsedCommand, Formatter, Command


class TestColorParsing(unittest.TestCase):
	"""Test color parsing functionality."""

	def test_parse_command_with_named_color(self):
		"""Test parsing command with named color."""
		result = parse("a#red=ls -la")
		expected = ParsedCommand(
			key="a",
			color="red",
			dependencies=[],
			redirects=None,
			actions=[],
			command=["ls", "-la"],
		)
		self.assertEqual(result, expected)

	def test_parse_command_with_hex_color(self):
		"""Test parsing command with hex color."""
		result = parse("a#00FF00=ls -la")
		expected = ParsedCommand(
			key="a",
			color="00FF00",
			dependencies=[],
			redirects=None,
			actions=[],
			command=["ls", "-la"],
		)
		self.assertEqual(result, expected)

	def test_parse_command_with_mixed_hex_case(self):
		"""Test parsing command with mixed case hex color."""
		result = parse("b#AbCdEf=echo hello")
		expected = ParsedCommand(
			key="b",
			color="AbCdEf",
			dependencies=[],
			redirects=None,
			actions=[],
			command=["echo", "hello"],
		)
		self.assertEqual(result, expected)

	def test_parse_command_without_color(self):
		"""Test parsing command without color specification."""
		result = parse("a=ls -la")
		expected = ParsedCommand(
			key="a",
			color=None,
			dependencies=[],
			redirects=None,
			actions=[],
			command=["ls", "-la"],
		)
		self.assertEqual(result, expected)

	def test_parse_command_with_color_and_delay(self):
		"""Test parsing command with both color and delay (now as dependency)."""
		result = parse("a#blue:DELAY+5s=ls -la")  # Updated format
		expected = ParsedCommand(
			key="a",
			color="blue",
			dependencies=[
				parse(":DELAY+5s=dummy").dependencies[0]  # Get the dependency structure
			],
			redirects=None,
			actions=[],
			command=["ls", "-la"],
		)
		# Simplified check - just verify the structure has the right components
		self.assertEqual(result.key, "a")
		self.assertEqual(result.color, "blue")
		self.assertEqual(len(result.dependencies), 1)
		self.assertEqual(result.dependencies[0].key, "DELAY")
		self.assertEqual(result.command, ["ls", "-la"])

	def test_parse_command_with_color_and_actions(self):
		"""Test parsing command with color and actions."""
		result = parse("a#cyan|silent=ls -la")
		expected = ParsedCommand(
			key="a",
			color="cyan",
			dependencies=[],
			redirects=None,
			actions=["silent"],
			command=["ls", "-la"],
		)
		self.assertEqual(result, expected)

	def test_parse_command_with_everything(self):
		"""Test parsing command with key, color, dependencies, and actions."""
		result = parse("worker#magenta:DELAY+2s500ms|silent=python script.py")
		# Verify the key components
		self.assertEqual(result.key, "worker")
		self.assertEqual(result.color, "magenta")
		self.assertEqual(len(result.dependencies), 1)
		self.assertEqual(result.dependencies[0].key, "DELAY")
		self.assertEqual(result.dependencies[0].delays, [2.5])  # 2s500ms = 2.5s
		self.assertEqual(result.actions, ["silent"])
		self.assertEqual(result.command, ["python", "script.py"])

	def test_parse_command_no_key_no_color(self):
		"""Test parsing command with no key and no color."""
		result = parse("ls -la")
		expected = ParsedCommand(
			key=None,
			color=None,
			dependencies=[],
			redirects=None,
			actions=[],
			command=["ls", "-la"],
		)
		self.assertEqual(result, expected)


class TestColorFormatter(unittest.TestCase):
	"""Test color formatting functionality."""

	def setUp(self):
		"""Set up test fixtures."""
		self.mock_writer = MagicMock()
		self.formatter = Formatter(writer=self.mock_writer)

	def test_get_color_code_named_colors(self):
		"""Test getting ANSI codes for named colors."""
		self.assertEqual(self.formatter._get_color_code("red"), "\033[31m")
		self.assertEqual(self.formatter._get_color_code("green"), "\033[32m")
		self.assertEqual(self.formatter._get_color_code("blue"), "\033[34m")
		self.assertEqual(self.formatter._get_color_code("bright_red"), "\033[91m")

	def test_get_color_code_hex_colors(self):
		"""Test getting ANSI codes for hex colors."""
		# Red: #FF0000 -> RGB(255, 0, 0)
		self.assertEqual(self.formatter._get_color_code("FF0000"), "\033[38;2;255;0;0m")
		# Green: #00FF00 -> RGB(0, 255, 0)
		self.assertEqual(self.formatter._get_color_code("00FF00"), "\033[38;2;0;255;0m")
		# Blue: #0000FF -> RGB(0, 0, 255)
		self.assertEqual(self.formatter._get_color_code("0000FF"), "\033[38;2;0;0;255m")

	def test_get_color_code_invalid(self):
		"""Test handling of invalid color codes."""
		self.assertEqual(self.formatter._get_color_code("invalid"), "")
		self.assertEqual(self.formatter._get_color_code("FFF"), "")  # Too short
		self.assertEqual(self.formatter._get_color_code("FFFFFFF"), "")  # Too long
		self.assertEqual(self.formatter._get_color_code("GGGGGG"), "")  # Invalid hex
		self.assertEqual(self.formatter._get_color_code(None), "")

	def test_apply_color_named(self):
		"""Test applying named colors to text."""
		result = self.formatter._apply_color("test", "red")
		expected = b"\033[31mtest\033[0m"
		self.assertEqual(result, expected)

	def test_apply_color_hex(self):
		"""Test applying hex colors to text."""
		result = self.formatter._apply_color("test", "FF0000")
		expected = b"\033[38;2;255;0;0mtest\033[0m"
		self.assertEqual(result, expected)

	def test_apply_color_none(self):
		"""Test applying no color to text."""
		result = self.formatter._apply_color("test", None)
		expected = b"test"
		self.assertEqual(result, expected)

	def test_format_with_color(self):
		"""Test formatting with color."""
		cmd = Command(["echo", "hello"], "test", "red")
		self.formatter.out(cmd, b"Hello World")

		# Verify the writer was called with colored output
		calls = self.mock_writer.call_args_list
		self.assertTrue(len(calls) > 0)

		# Check that colored key is included in one of the calls
		colored_key_found = any(b"\033[31mtest\033[0m" in call[0][0] for call in calls)
		self.assertTrue(colored_key_found, "Colored key not found in output")

	def test_format_without_color(self):
		"""Test formatting without color."""
		cmd = Command(["echo", "hello"], "test", None)
		self.formatter.out(cmd, b"Hello World")

		# Verify the writer was called
		calls = self.mock_writer.call_args_list
		self.assertTrue(len(calls) > 0)

		# Check that no ANSI codes are present
		ansi_found = any(b"\033[" in call[0][0] for call in calls)
		self.assertFalse(ansi_found, "ANSI codes found in non-colored output")


if __name__ == "__main__":
	unittest.main()
