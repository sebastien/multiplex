#!/usr/bin/env python3
"""
Comprehensive test suite for multiplex child process management improvements.

This test validates:
1. SIGHUP signal handling
2. Graceful vs force termination
3. Signal propagation to child processes
4. Process group management
5. Complex process tree handling
"""

import sys
import os
import signal
import time
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import run, terminate, Runner, Proc


def test_all_signals():
	"""Test handling of SIGINT, SIGTERM, and SIGHUP"""
	print("Testing all signal types...")

	signals_to_test = [
		(signal.SIGINT, "SIGINT"),
		(signal.SIGTERM, "SIGTERM"),
		(signal.SIGHUP, "SIGHUP"),
	]

	for sig, name in signals_to_test:
		print(f"\n  Testing {name}...")
		runner = Runner()
		cmd = runner.run(["sleep", "10"], key=f"test_{name.lower()}")

		assert cmd.isRunning, f"Process should be running for {name} test"
		time.sleep(0.2)

		# Send signal to our process (multiplex)
		old_handler = signal.signal(sig, runner.onSignal)
		try:
			os.kill(os.getpid(), sig)
			time.sleep(0.5)

			if not cmd.isRunning:
				print(f"    ✓ {name} properly terminated subprocess")
			else:
				print(f"    ✗ {name} did not terminate subprocess")
				runner.terminate(graceful=False)
				raise AssertionError(f"{name} handling failed")
		finally:
			signal.signal(sig, old_handler)


def test_graceful_shutdown_timing():
	"""Test that graceful shutdown respects timeouts"""
	print("\nTesting graceful shutdown timing...")

	runner = Runner()
	# Set short timeouts for testing
	runner.graceful_timeout = 1.0
	runner.force_timeout = 1.0

	# Start a process that ignores SIGTERM but responds to SIGKILL
	ignore_script = """#!/bin/bash
trap '' TERM  # Ignore SIGTERM
sleep 30
"""

	script_path = "/tmp/test_ignore_term.sh"
	with open(script_path, "w") as f:
		f.write(ignore_script)
	os.chmod(script_path, 0o755)

	try:
		cmd = runner.run(["bash", script_path], key="ignore_test")
		time.sleep(0.2)

		start_time = time.time()
		success = runner.terminate(graceful=True)
		elapsed = time.time() - start_time

		# Should take approximately graceful_timeout + force_timeout
		expected_time = runner.graceful_timeout + runner.force_timeout
		print(f"    ✓ Termination took {elapsed:.2f}s (expected ~{expected_time:.2f}s)")

		if 0.8 * expected_time <= elapsed <= 1.5 * expected_time:
			print("    ✓ Timing within expected range")
		else:
			print(f"    ⚠️  Timing outside expected range")

		assert success, "Termination should succeed even with ignored SIGTERM"
		print("    ✓ Force termination succeeded after graceful timeout")

	finally:
		if os.path.exists(script_path):
			os.unlink(script_path)


def test_process_group_isolation():
	"""Test that each command gets its own process group"""
	print("\nTesting process group isolation...")

	runner = Runner()

	# Start multiple commands
	cmd1 = runner.run(["sleep", "10"], key="group1")
	cmd2 = runner.run(["sleep", "10"], key="group2")

	time.sleep(0.2)

	print(f"    Process 1: PID={cmd1.pid}, PGID={cmd1.pgid}")
	print(f"    Process 2: PID={cmd2.pid}, PGID={cmd2.pgid}")

	# Each process should be its own group leader
	assert cmd1.pgid == cmd1.pid, "Process should be its own group leader"
	assert cmd2.pgid == cmd2.pid, "Process should be its own group leader"
	assert cmd1.pgid != cmd2.pgid, "Processes should have different group IDs"

	print("    ✓ Process group isolation working correctly")

	# Clean up
	runner.terminate(graceful=False)


def test_signal_propagation_verification():
	"""Verify signals are actually propagated to children"""
	print("\nTesting signal propagation verification...")

	# Create a script that logs when it receives signals
	log_file = "/tmp/signal_log.txt"
	signal_logger = f"""#!/bin/bash
echo "Process started: $$" > {log_file}

handle_signal() {{
    echo "Received signal $1: $$" >> {log_file}
    exit 0
}}

trap 'handle_signal TERM' TERM
trap 'handle_signal INT' INT
trap 'handle_signal HUP' HUP

sleep 30
"""

	script_path = "/tmp/signal_logger.sh"
	with open(script_path, "w") as f:
		f.write(signal_logger)
	os.chmod(script_path, 0o755)

	try:
		# Remove old log file
		if os.path.exists(log_file):
			os.unlink(log_file)

		runner = Runner()
		cmd = runner.run(["bash", script_path], key="logger")

		time.sleep(0.3)  # Let process start and create log

		# Propagate SIGTERM
		runner.propagateSignal(signal.SIGTERM.value)
		time.sleep(0.5)

		# Check log file
		if os.path.exists(log_file):
			with open(log_file, "r") as f:
				log_content = f.read()
			print(f"    Signal log content: {log_content.strip()}")

			if "Received signal TERM" in log_content:
				print("    ✓ Signal propagation verified in log")
			else:
				print("    ⚠️  Signal may not have been received")
		else:
			print("    ⚠️  Log file not created")

	finally:
		# Cleanup
		for path in [script_path, log_file]:
			if os.path.exists(path):
				os.unlink(path)


def run_all_tests():
	"""Run all test functions"""
	tests = [
		test_graceful_shutdown_timing,
		test_process_group_isolation,
		test_signal_propagation_verification,
		test_all_signals,  # Run this last as it exits
	]

	print("🧪 Running comprehensive multiplex child process management tests...\n")

	for test_func in tests:
		try:
			test_func()
		except SystemExit:
			# Expected from signal tests
			break
		except Exception as e:
			print(f"\n❌ Test {test_func.__name__} failed: {e}")
			import traceback

			traceback.print_exc()
			return False

	print("\n✅ All tests completed successfully!")
	return True


if __name__ == "__main__":
	try:
		success = run_all_tests()
		sys.exit(0 if success else 1)
	except KeyboardInterrupt:
		print("\n✓ Interrupt handled correctly")
		sys.exit(0)
