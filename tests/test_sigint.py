"""Module: test_sigint — tests multiplex behavior."""

from __future__ import annotations

import signal
import time

import pytest
from multiplex import Runner


def test_sigint_handling():
	"""Test that SIGINT (Ctrl-C) properly terminates subprocesses"""
	print("Testing SIGINT handling...")

	# Start a long-running process
	runner = Runner()
	cmd = runner.run(["sleep", "10"], key="test")

	# Verify the process is running
	assert cmd.is_running, "Process should be running"
	print(f"✓ Process {cmd.pid} is running")

	# Wait a bit to ensure process is fully started
	time.sleep(0.5)

	with pytest.raises(SystemExit, match="0"):
		runner.on_signal(signal.SIGINT, None)
	assert not cmd.is_running


def test_manual_termination():
	"""Test manual termination works correctly"""
	print("\nTesting manual termination...")

	runner = Runner()
	cmd = runner.run(["sleep", "5"], key="test2")

	assert cmd.is_running, "Process should be running"
	print(f"✓ Process {cmd.pid} is running")

	# Manually terminate
	runner.terminate()

	# Wait for termination to complete
	time.sleep(1)

	if not cmd.is_running:
		print("✓ Manual termination successful")
	else:
		print("✗ Manual termination failed")
		raise AssertionError("Manual termination failed")
# EOF
