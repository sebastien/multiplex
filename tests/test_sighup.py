"""Module: test_sighup — tests multiplex behavior."""

from __future__ import annotations

import signal
import time

import pytest
from multiplex import Runner


def test_sighup_handling():
	"""Test that SIGHUP properly terminates subprocesses gracefully"""
	print("Testing SIGHUP handling...")

	# Start a long-running process
	runner = Runner()
	cmd = runner.run(["sleep", "10"], key="test")

	# Verify the process is running
	assert cmd.is_running, "Process should be running"
	print(f"✓ Process {cmd.pid} is running")

	# Wait a bit to ensure process is fully started
	time.sleep(0.5)

	with pytest.raises(SystemExit, match="0"):
		runner.on_signal(signal.SIGHUP, None)
	assert not cmd.is_running


def test_graceful_vs_force():
	"""Test graceful vs force termination"""
	print("\nTesting graceful vs force termination...")

	runner = Runner()

	# Test graceful termination
	cmd1 = runner.run(["sleep", "2"], key="graceful")
	time.sleep(0.1)

	start_time = time.time()
	success = runner.terminate(cmd1, graceful=True)
	elapsed = time.time() - start_time

	print(f"✓ Graceful termination took {elapsed:.2f}s, success: {success}")

	# Test force termination
	cmd2 = runner.run(["sleep", "10"], key="force")
	time.sleep(0.1)

	start_time = time.time()
	success = runner.terminate(cmd2, graceful=False)
	elapsed = time.time() - start_time

	print(f"✓ Force termination took {elapsed:.2f}s, success: {success}")
# EOF
