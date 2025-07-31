#!/usr/bin/env python3
"""
Test suite for macOS compatibility of multiplex.py

This test verifies that the Proc class methods work correctly on both
Linux (with /proc) and macOS (with fallback implementations).
"""

import os
import sys
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the src directory to the path to import multiplex
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "py"))
import multiplex


class TestMacOSCompatibility(unittest.TestCase):
	"""Test macOS compatibility for the Proc class methods."""

	def setUp(self):
		"""Set up test environment."""
		# Start a test process that we can use for testing
		self.test_process = subprocess.Popen(
			[sys.executable, "-c", "import time; time.sleep(30)"]
		)
		self.test_pid = self.test_process.pid
		# Give process time to start
		time.sleep(0.1)

	def tearDown(self):
		"""Clean up test environment."""
		try:
			self.test_process.terminate()
			self.test_process.wait(timeout=5)
		except (subprocess.TimeoutExpired, ProcessLookupError):
			try:
				self.test_process.kill()
				self.test_process.wait(timeout=5)
			except (subprocess.TimeoutExpired, ProcessLookupError):
				pass

	def test_proc_availability_detection(self):
		"""Test that platform detection works correctly."""
		# The _HAS_PROC variable should be set based on /proc existence
		has_proc_dir = Path("/proc").exists()
		self.assertEqual(multiplex._HAS_PROC, has_proc_dir)

	def test_proc_exists_with_valid_pid(self):
		"""Test Proc.exists() with a valid PID."""
		# Test with our test process
		self.assertTrue(multiplex.Proc.exists(self.test_pid))

		# Test with current process
		self.assertTrue(multiplex.Proc.exists(os.getpid()))

	def test_proc_exists_with_invalid_pid(self):
		"""Test Proc.exists() with an invalid PID."""
		# Use a PID that's very unlikely to exist
		invalid_pid = 999999
		self.assertFalse(multiplex.Proc.exists(invalid_pid))

	def test_proc_parent_with_valid_pid(self):
		"""Test Proc.parent() with a valid PID."""
		# Get parent PID of our test process
		parent_pid = multiplex.Proc.parent(self.test_pid)

		# Should return current process PID as parent
		self.assertEqual(parent_pid, os.getpid())

	def test_proc_parent_with_invalid_pid(self):
		"""Test Proc.parent() with an invalid PID."""
		# Use a PID that's very unlikely to exist
		invalid_pid = 999999
		parent_pid = multiplex.Proc.parent(invalid_pid)
		self.assertIsNone(parent_pid)

	def test_proc_mem_with_valid_pid(self):
		"""Test Proc.mem() with a valid PID."""
		# Get memory info for our test process
		mem_current, mem_peak = multiplex.Proc.mem(self.test_pid)

		# Should return memory values in proper format
		self.assertIsInstance(mem_current, str)
		self.assertIsInstance(mem_peak, str)
		self.assertTrue(mem_current.endswith(" kB"))
		self.assertTrue(mem_peak.endswith(" kB"))

		# Memory values should be positive integers
		current_val = int(mem_current.replace(" kB", ""))
		peak_val = int(mem_peak.replace(" kB", ""))
		self.assertGreater(current_val, 0)
		self.assertGreater(peak_val, 0)

	def test_proc_mem_with_invalid_pid(self):
		"""Test Proc.mem() with an invalid PID."""
		# Use a PID that's very unlikely to exist
		invalid_pid = 999999
		mem_current, mem_peak = multiplex.Proc.mem(invalid_pid)

		# Should return zero values
		self.assertEqual(mem_current, "0 kB")
		self.assertEqual(mem_peak, "0 kB")

	def test_proc_children(self):
		"""Test Proc.children() method."""
		# This method already uses ps and should work cross-platform
		children = multiplex.Proc.children(self.test_pid)
		self.assertIsInstance(children, set)
		# Children set might be empty for our simple test process

	@patch("multiplex._HAS_PROC", False)
	def test_fallback_implementation_forced(self):
		"""Test that fallback implementations work when forced."""
		# Force using fallback implementations

		# Test exists
		self.assertTrue(multiplex.Proc.exists(self.test_pid))
		self.assertFalse(multiplex.Proc.exists(999999))

		# Test parent
		parent_pid = multiplex.Proc.parent(self.test_pid)
		self.assertEqual(parent_pid, os.getpid())

		# Test mem
		mem_current, mem_peak = multiplex.Proc.mem(self.test_pid)
		self.assertTrue(mem_current.endswith(" kB"))
		self.assertTrue(mem_peak.endswith(" kB"))

	def test_fallback_shell_command_failures(self):
		"""Test fallback behavior when shell commands fail."""
		# Mock shell to return None (command failure)
		with patch("multiplex.shell", return_value=None):
			with patch("multiplex._HAS_PROC", False):
				# parent() should return None when ps fails
				self.assertIsNone(multiplex.Proc.parent(self.test_pid))

				# mem() should return "0 kB" when ps fails
				mem_current, mem_peak = multiplex.Proc.mem(self.test_pid)
				self.assertEqual(mem_current, "0 kB")
				self.assertEqual(mem_peak, "0 kB")

	def test_fallback_shell_command_malformed_output(self):
		"""Test fallback behavior when shell commands return malformed output."""
		# Mock shell to return malformed data
		with patch("multiplex.shell", return_value=b"invalid output format"):
			with patch("multiplex._HAS_PROC", False):
				# parent() should return None when ps output is malformed
				self.assertIsNone(multiplex.Proc.parent(self.test_pid))

				# mem() should return "0 kB" when ps output is malformed
				mem_current, mem_peak = multiplex.Proc.mem(self.test_pid)
				self.assertEqual(mem_current, "0 kB")
				self.assertEqual(mem_peak, "0 kB")

	def test_command_integration(self):
		"""Test that Command class works with the updated Proc methods."""
		# Create a command and test its properties
		cmd = multiplex.Command(["echo", "test"], "test")
		cmd.pid = self.test_pid

		# Test that command can check if it's running
		self.assertTrue(cmd.isRunning)

		# Test parent PID access
		self.assertIsNotNone(cmd.ppid)
		self.assertEqual(cmd.ppid, os.getpid())

	def test_runner_integration(self):
		"""Test that Runner works with cross-platform Proc methods."""
		runner = multiplex.Runner()

		# Run a simple command
		cmd = runner.run(["echo", "Hello, World!"], key="test")

		# Wait for command to complete
		runner.join(timeout=5)

		# Command should have completed successfully
		self.assertIsNotNone(cmd.pid)


class TestPlatformSpecificBehavior(unittest.TestCase):
	"""Test platform-specific behavior differences."""

	def test_linux_proc_vs_macos_fallback(self):
		"""Compare Linux /proc vs macOS fallback when both are available."""
		if not Path("/proc").exists():
			self.skipTest("This test requires /proc filesystem")

		# Start a test process
		test_process = subprocess.Popen(
			[sys.executable, "-c", "import time; time.sleep(5)"]
		)
		test_pid = test_process.pid

		try:
			# Test with /proc enabled
			with patch("multiplex._HAS_PROC", True):
				exists_proc = multiplex.Proc.exists(test_pid)
				parent_proc = multiplex.Proc.parent(test_pid)
				mem_proc = multiplex.Proc.mem(test_pid)

			# Test with fallback enabled
			with patch("multiplex._HAS_PROC", False):
				exists_fallback = multiplex.Proc.exists(test_pid)
				parent_fallback = multiplex.Proc.parent(test_pid)
				mem_fallback = multiplex.Proc.mem(test_pid)

			# Results should be consistent
			self.assertEqual(exists_proc, exists_fallback)
			self.assertEqual(parent_proc, parent_fallback)

			# Memory format should be consistent (both should end with " kB")
			self.assertTrue(mem_proc[0].endswith(" kB"))
			self.assertTrue(mem_proc[1].endswith(" kB"))
			self.assertTrue(mem_fallback[0].endswith(" kB"))
			self.assertTrue(mem_fallback[1].endswith(" kB"))

		finally:
			try:
				test_process.terminate()
				test_process.wait(timeout=5)
			except (subprocess.TimeoutExpired, ProcessLookupError):
				try:
					test_process.kill()
					test_process.wait(timeout=5)
				except (subprocess.TimeoutExpired, ProcessLookupError):
					pass


if __name__ == "__main__":
	print(f"Running macOS compatibility tests...")
	print(f"Platform has /proc: {multiplex._HAS_PROC}")
	print(f"Python version: {sys.version}")
	print(f"Platform: {sys.platform}")
	print()

	unittest.main(verbosity=2)
