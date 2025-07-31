#!/usr/bin/env python3
"""Runtime test for redirect functionality.

This tests the actual execution behavior of redirects to ensure
that stdin redirection from process outputs works correctly.
"""

import sys
import os
import time
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/py"))

from multiplex import Runner, parse


def test_simple_stdout_redirect():
	"""Test that stdout redirect actually works at runtime"""
	runner = Runner()

	# Start a process that produces output
	parsed_a = parse("A=echo 'hello from A'")
	cmd_a = runner.run(
		parsed_a.command,
		key=parsed_a.key,
		dependencies=parsed_a.dependencies,
		redirects=parsed_a.redirects,
		actions=parsed_a.actions,
	)

	# Small delay to let A produce output
	time.sleep(0.1)

	# Start a process that consumes A's stdout
	parsed_b = parse("<A=cat")
	cmd_b = runner.run(
		parsed_b.command,
		key="B",
		dependencies=parsed_b.dependencies,
		redirects=parsed_b.redirects,
		actions=parsed_b.actions,
	)

	# Wait for both to complete
	runner.join([cmd_a, cmd_b], timeout=2.0)

	print("✓ Simple stdout redirect runtime test completed")


def test_stderr_redirect():
	"""Test that stderr redirect works at runtime"""
	runner = Runner()

	# Start a process that produces stderr output using a more portable approach
	parsed_a = parse("A=python3 -c 'import sys; sys.stderr.write(\"error from A\\n\")'")
	cmd_a = runner.run(
		parsed_a.command,
		key=parsed_a.key,
		dependencies=parsed_a.dependencies,
		redirects=parsed_a.redirects,
		actions=parsed_a.actions,
	)

	# Small delay to let A produce output
	time.sleep(0.1)

	# Start a process that consumes A's stderr
	parsed_b = parse("<2A=cat")
	cmd_b = runner.run(
		parsed_b.command,
		key="B",
		dependencies=parsed_b.dependencies,
		redirects=parsed_b.redirects,
		actions=parsed_b.actions,
	)

	# Wait for both to complete
	runner.join([cmd_a, cmd_b], timeout=2.0)

	print("✓ Stderr redirect runtime test completed")


def test_combined_streams_redirect():
	"""Test that combined stdout and stderr redirect works"""
	runner = Runner()

	# Start a process that produces both stdout and stderr
	parsed_a = parse(
		'A=python3 -c \'print("stdout"); import sys; sys.stderr.write("stderr\\n")\''
	)
	cmd_a = runner.run(
		parsed_a.command,
		key=parsed_a.key,
		dependencies=parsed_a.dependencies,
		redirects=parsed_a.redirects,
		actions=parsed_a.actions,
	)

	# Small delay to let A produce output
	time.sleep(0.1)

	# Start a process that consumes both A's stdout and stderr
	parsed_b = parse("<(1A,2A)=cat")
	cmd_b = runner.run(
		parsed_b.command,
		key="B",
		dependencies=parsed_b.dependencies,
		redirects=parsed_b.redirects,
		actions=parsed_b.actions,
	)

	# Wait for both to complete
	runner.join([cmd_a, cmd_b], timeout=2.0)

	print("✓ Combined streams redirect runtime test completed")


if __name__ == "__main__":
	print("Running redirect runtime tests...\n")

	try:
		test_simple_stdout_redirect()
		test_stderr_redirect()
		test_combined_streams_redirect()
		print("\n✅ All redirect runtime tests completed!")
	except Exception as e:
		print(f"\n❌ Runtime test failed: {e}")
		import traceback

		traceback.print_exc()
