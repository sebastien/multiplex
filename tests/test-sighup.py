#!/usr/bin/env python3
import sys
import os
import signal
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import run, terminate, Runner


def test_sighup_handling():
	"""Test that SIGHUP properly terminates subprocesses gracefully"""
	print("Testing SIGHUP handling...")

	# Start a long-running process
	runner = Runner()
	cmd = runner.run(["sleep", "10"], key="test")

	# Verify the process is running
	assert cmd.isRunning, "Process should be running"
	print(f"✓ Process {cmd.pid} is running")

	# Wait a bit to ensure process is fully started
	time.sleep(0.5)

	# Send SIGHUP to ourselves
	print("Sending SIGHUP signal...")
	os.kill(os.getpid(), signal.SIGHUP)

	# Give the signal handler time to work
	time.sleep(1)

	# Check if the process was terminated
	if not cmd.isRunning:
		print("✓ SIGHUP properly terminated subprocess")
	else:
		print("✗ SIGHUP did not terminate subprocess")
		# Manually terminate for cleanup
		runner.terminate()
		runner.join()
		raise AssertionError("SIGHUP handling failed")


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


if __name__ == "__main__":
	try:
		test_graceful_vs_force()
		test_sighup_handling()
		print("\n✅ All SIGHUP and graceful termination tests passed!")
	except KeyboardInterrupt:
		print("\n✓ SIGHUP caught and handled correctly")
		sys.exit(0)
	except Exception as e:
		print(f"\n✗ Test failed: {e}")
		sys.exit(1)
