"""Tests for input guards (`!GUARD`) and process guards (`KEY|GUARD`)."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from multiplex import (
	Dependency,
	InputGuard,
	ProcessGuard,
	Runner,
	Wait,
	parse,
	parse_dependencies,
	parse_guard_definition,
)

ROOT = Path(__file__).parent.parent


def test_guard_definition_parsing():
	"""Guard definitions accept globs and `:re` regular expressions."""
	assert parse_guard_definition("@ready=*Ready*") == ("ready", "*Ready*", False)
	assert parse_guard_definition("@ready:re=Ready!?") == ("ready", "Ready!?", True)
	assert parse_guard_definition("A=echo hello") is None
	print("✓ Guard definition parsing")


def test_guard_step_parsing():
	"""Guard steps appear in start and dependency chains."""
	assert parse_dependencies(":A!READY") == [
		Dependency("A", False, [InputGuard("READY")])
	]
	assert parse_dependencies(":A+!READY") == [
		Dependency("A", False, [InputGuard("READY")])
	]

	start = parse("+A|READY=echo hi")
	assert start.start_steps == [ProcessGuard("A", (1,), "READY")], start

	both = parse("+A(1,2)|READY=echo hi")
	assert both.start_steps == [ProcessGuard("A", (1, 2), "READY")], both

	chained = parse("+A!READY+10s=echo hi")
	assert chained.start_steps == [Wait("A", False), InputGuard("READY"), 10.0], chained
	assert chained.start_delay == 0.0, chained

	# `|silent` remains an action, not a guard binding.
	action = parse("+A|silent=echo hi")
	assert action.start_steps == [Wait("A", False)], action
	assert action.actions == ["silent"], action
	print("✓ Guard step parsing")


def test_process_guard_runtime():
	"""A process guard unblocks a consumer once the producer matches."""
	runner = Runner()
	runner.define_guard("READY", "*Ready*")
	started = time.time()
	runner.run(["bash", "-c", "sleep 0.2; echo Ready!"], key="A")
	runner.run(
		["echo", "GO"], key="B", start_steps=[ProcessGuard("A", (1,), "READY")]
	)
	runner.join()
	elapsed = time.time() - started
	assert elapsed >= 0.2, elapsed
	print(f"✓ Process guard unblocked after {elapsed:.2f}s")


def test_process_guard_latching():
	"""A guard already matched from buffered output does not wait again."""
	runner = Runner()
	runner.define_guard("READY", "*Ready*")
	runner.run(["bash", "-c", "echo Ready!"], key="A")
	time.sleep(0.3)
	started = time.time()
	runner.run(
		["echo", "GO"], key="B", start_steps=[ProcessGuard("A", (1,), "READY")]
	)
	runner.join()
	elapsed = time.time() - started
	assert elapsed < 0.5, elapsed
	print("✓ Process guard latches from buffered output")


def test_regex_guard_runtime():
	"""A regular-expression guard matches producer output."""
	runner = Runner()
	runner.define_guard("PORT", r"listening on \d+", True)
	runner.run(["bash", "-c", "sleep 0.1; echo listening on 8080"], key="A")
	runner.run(
		["echo", "GO"], key="B", start_steps=[ProcessGuard("A", (1,), "PORT")]
	)
	runner.join()
	print("✓ Regex guard matching")


def test_undefined_guard():
	"""Waiting on an undefined guard raises a clear error."""
	runner = Runner()
	try:
		runner.run(["echo", "x"], key="B", start_steps=[InputGuard("MISSING")])
		assert False, "Should have raised for an undefined guard"
	except ValueError as error:
		assert "Undefined guard" in str(error), error
	print("✓ Undefined guard error")


def test_input_guard_cli():
	"""The CLI reads stdin and starts a command once a guard matches."""
	result = subprocess.run(
		[sys.executable, "-m", "multiplex", "@READY=*Ready*", "!READY=echo GO"],
		cwd=ROOT / "src" / "py",
		input=b"warming up\nReady to go\n",
		capture_output=True,
		timeout=10,
	)
	assert result.returncode == 0, result.stderr
	assert b"GO" in result.stdout, result.stdout
	print("✓ Input guard via CLI stdin")


def main():
	print("Running guard feature tests...\n")
	test_guard_definition_parsing()
	test_guard_step_parsing()
	test_process_guard_runtime()
	test_process_guard_latching()
	test_regex_guard_runtime()
	test_undefined_guard()
	test_input_guard_cli()
	print("\n✅ All guard tests passed!")
	return 0
# EOF
