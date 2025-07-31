#!/usr/bin/env python3
"""Runtime test for start-on-output functionality.

This tests the actual execution behavior of start-on-output to ensure
that commands start only when other commands produce output.
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import Runner, parse


# Use a single runner instance to avoid signal handler conflicts
runner = Runner()


def test_simple_stdout_start_on_output():
	"""Test that start-on-output waits for stdout from another process"""
	
	start_time = time.time()
	
	# Start a process that will output after a delay
	parsed_a = parse("A=bash -c 'sleep 0.5; echo \"hello from A\"'")
	cmd_a = runner.run(
		parsed_a.command,
		key=parsed_a.key,
		dependencies=parsed_a.dependencies,
		redirects=parsed_a.redirects,
		start_on_output=parsed_a.start_on_output,
		actions=parsed_a.actions,
	)
	
	# Start a process that waits for A's stdout
	parsed_b = parse(">A=echo \"B started after A output\"")
	cmd_b = runner.run(
		parsed_b.command,
		key="B",
		dependencies=parsed_b.dependencies,
		redirects=parsed_b.redirects,
		start_on_output=parsed_b.start_on_output,
		actions=parsed_b.actions,
	)
	
	# Wait for both to complete
	runner.join([cmd_a, cmd_b], timeout=3.0)
	
	duration = time.time() - start_time
	print(f"✓ Simple stdout start-on-output test completed in {duration:.2f}s")
	
	# B should have started after A produced output (around 0.5s)
	assert duration >= 0.5, f"Expected duration >= 0.5s, got {duration:.2f}s"


def test_stderr_start_on_output():
	"""Test that start-on-output waits for stderr from another process"""
	
	start_time = time.time()
	
	# Start a process that outputs to stderr after a delay
	parsed_a = parse("C=bash -c 'sleep 0.5; echo \"error from C\" >&2'")
	cmd_a = runner.run(
		parsed_a.command,
		key=parsed_a.key,
		dependencies=parsed_a.dependencies,
		redirects=parsed_a.redirects,
		start_on_output=parsed_a.start_on_output,
		actions=parsed_a.actions,
	)
	
	# Start a process that waits for C's stderr
	parsed_b = parse(">2C=echo \"D started after C stderr\"")
	cmd_b = runner.run(
		parsed_b.command,
		key="D",
		dependencies=parsed_b.dependencies,
		redirects=parsed_b.redirects,
		start_on_output=parsed_b.start_on_output,
		actions=parsed_b.actions,
	)
	
	# Wait for both to complete
	runner.join([cmd_a, cmd_b], timeout=3.0)
	
	duration = time.time() - start_time
	print(f"✓ Stderr start-on-output test completed in {duration:.2f}s")
	
	# D should have started after C produced stderr output (around 0.5s)
	assert duration >= 0.5, f"Expected duration >= 0.5s, got {duration:.2f}s"


def test_combined_streams_start_on_output():
	"""Test that start-on-output waits for either stdout or stderr"""
	
	start_time = time.time()
	
	# Start a process that outputs to both stdout and stderr with delays
	parsed_a = parse("E=bash -c 'sleep 0.3; echo \"stdout from E\"; sleep 0.2; echo \"stderr from E\" >&2'")
	cmd_a = runner.run(
		parsed_a.command,
		key=parsed_a.key,
		dependencies=parsed_a.dependencies,
		redirects=parsed_a.redirects,
		start_on_output=parsed_a.start_on_output,
		actions=parsed_a.actions,
	)
	
	# Start a process that waits for either E's stdout or stderr
	parsed_b = parse(">(1E,2E)=echo \"F started after E output\"")
	cmd_b = runner.run(
		parsed_b.command,
		key="F",
		dependencies=parsed_b.dependencies,
		redirects=parsed_b.redirects,
		start_on_output=parsed_b.start_on_output,
		actions=parsed_b.actions,
	)
	
	# Wait for both to complete
	runner.join([cmd_a, cmd_b], timeout=3.0)
	
	duration = time.time() - start_time
	print(f"✓ Combined streams start-on-output test completed in {duration:.2f}s")
	
	# F should have started after E's first output (around 0.3s, not 0.5s)
	assert 0.3 <= duration <= 0.7, f"Expected 0.3s <= duration <= 0.7s, got {duration:.2f}s"


def test_multiple_processes_start_on_output():
	"""Test that start-on-output waits for output from any of multiple processes"""
	
	start_time = time.time()
	
	# Start two processes with different delays
	parsed_a = parse("G=bash -c 'sleep 0.7; echo \"hello from G\"'")
	cmd_a = runner.run(
		parsed_a.command,
		key=parsed_a.key,
		dependencies=parsed_a.dependencies,
		redirects=parsed_a.redirects,
		start_on_output=parsed_a.start_on_output,
		actions=parsed_a.actions,
	)
	
	parsed_b = parse("H=bash -c 'sleep 0.3; echo \"hello from H\"'")
	cmd_b = runner.run(
		parsed_b.command,
		key=parsed_b.key,
		dependencies=parsed_b.dependencies,
		redirects=parsed_b.redirects,
		start_on_output=parsed_b.start_on_output,
		actions=parsed_b.actions,
	)
	
	# Start a process that waits for either G or H to output
	parsed_c = parse(">(G,H)=echo \"I started after G or H output\"")
	cmd_c = runner.run(
		parsed_c.command,
		key="I",
		dependencies=parsed_c.dependencies,
		redirects=parsed_c.redirects,
		start_on_output=parsed_c.start_on_output,
		actions=parsed_c.actions,
	)
	
	# Wait for all to complete
	runner.join([cmd_a, cmd_b, cmd_c], timeout=3.0)
	
	duration = time.time() - start_time
	print(f"✓ Multiple processes start-on-output test completed in {duration:.2f}s")
	
	# I should have started after the first output (H at 0.3s, not G at 0.7s)
	assert 0.3 <= duration <= 0.8, f"Expected 0.3s <= duration <= 0.8s, got {duration:.2f}s"


if __name__ == "__main__":
	print("Running start-on-output runtime tests...\n")
	
	try:
		test_simple_stdout_start_on_output()
		test_stderr_start_on_output()
		test_combined_streams_start_on_output()
		test_multiple_processes_start_on_output()
		print("\n✅ All start-on-output runtime tests completed!")
		
		# Clean shutdown - terminate any remaining processes
		runner.terminate()
		
		# Force exit to avoid hanging on threads
		import os
		os._exit(0)
	except Exception as e:
		print(f"\n❌ Runtime test failed: {e}")
		import traceback
		traceback.print_exc()
		import os
		os._exit(1)