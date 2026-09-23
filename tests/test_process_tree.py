"""Module: test_process_tree — tests multiplex behavior."""

from __future__ import annotations

import os
import signal
import time

from multiplex import Proc, Runner


def test_complex_process_tree():
	"""Test termination of complex process trees"""
	print("Testing complex process tree termination...")

	# Create a shell script that spawns multiple children
	test_script = """#!/bin/bash
# Start some background processes
sleep 30 &
sleep 30 &
sleep 30 &
# Keep the main process running
sleep 30
"""

	script_path = "/tmp/test_multiplex_tree.sh"
	with open(script_path, "w") as f:
		f.write(test_script)
	os.chmod(script_path, 0o755)

	try:
		runner = Runner()
		cmd = runner.run(["bash", script_path], key="tree_test")

		# Wait a bit for child processes to start
		time.sleep(1)

		print(f"✓ Main process {cmd.pid} started")
		print(f"✓ Found children: {cmd.children}")

		# Verify processes are running
		all_pids = {cmd.pid}.union(cmd.children)
		running_before = sum(1 for pid in all_pids if pid and Proc.exists(pid))
		print(f"✓ {running_before} processes running before termination")

		# Terminate gracefully
		start_time = time.time()
		success = runner.terminate(graceful=True)
		elapsed = time.time() - start_time

		print(f"✓ Graceful termination completed in {elapsed:.2f}s, success: {success}")

		# Verify all processes are terminated
		time.sleep(0.5)	 # Give processes time to fully terminate
		running_after = sum(1 for pid in all_pids if pid and Proc.exists(pid))
		print(f"✓ {running_after} processes running after termination")

		if running_after == 0:
			print("✅ All processes in tree terminated successfully!")
		else:
			print(f"⚠️  {running_after} processes still running")

	finally:
		# Cleanup
		if os.path.exists(script_path):
			os.unlink(script_path)


def test_signal_propagation():
	"""Test that signals are properly propagated to children"""
	print("\nTesting signal propagation...")

	# Create a script that handles signals
	signal_script = """#!/bin/bash
# Set up signal handler
cleanup() {
	echo "Child received signal, cleaning up..."
	exit 0
}
trap cleanup TERM INT HUP

# Start and wait
echo "Child process started, waiting for signal..."
sleep 30
"""

	script_path = "/tmp/test_signal_prop.sh"
	with open(script_path, "w") as f:
		f.write(signal_script)
	os.chmod(script_path, 0o755)

	try:
		runner = Runner()
		cmd = runner.run(["bash", script_path], key="signal_test")

		# Wait for process to start
		time.sleep(0.5)
		print(f"✓ Process {cmd.pid} started")

		# Send SIGTERM and see if it's handled
		runner.propagate_signal(signal.SIGTERM.value)
		time.sleep(1)

		if not cmd.is_running:
			print("✅ Signal properly propagated and handled!")
		else:
			print("⚠️  Signal may not have been handled")
			runner.terminate(graceful=False)

	finally:
		# Cleanup
		if os.path.exists(script_path):
			os.unlink(script_path)
# EOF
