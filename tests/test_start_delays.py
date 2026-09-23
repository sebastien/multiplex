"""
Test cases for the new start delay functionality.

Tests the new format: [KEY][#COLOR][+DELAY…][:DEP…][|ACTION…]=COMMAND
"""

from __future__ import annotations

import time

# Add the src directory to the path
from multiplex import Runner, Wait, parse


def test_parse_start_delays():
	"""Test parsing of various start delay formats"""

	# Test basic start delay
	result = parse("+2=echo hello")
	assert result.key is None
	assert result.color is None
	assert result.start_delay == 2.0
	assert result.dependencies == []
	assert result.actions == []
	assert result.command == ['echo', 'hello']
	print("✓ Basic start delay parsing")

	# Test key with start delay
	result = parse("API+2=echo hello")
	assert result.key == "API"
	assert result.color is None
	assert result.start_delay == 2.0
	print("✓ Key with start delay parsing")

	# Test color with start delay
	result = parse("#blue+2=echo hello")
	assert result.key is None
	assert result.color == "blue"
	assert result.start_delay == 2.0
	print("✓ Color with start delay parsing")

	# Test key and color with start delay
	result = parse("API#blue+2=echo hello")
	assert result.key == "API"
	assert result.color == "blue"
	assert result.start_delay == 2.0
	print("✓ Key and color with start delay parsing")

	# Test start delay with dependencies
	result = parse("API+2:DB=echo hello")
	assert result.key == "API"
	assert result.start_delay == 2.0
	assert len(result.dependencies) == 1
	assert result.dependencies[0].key == "DB"
	print("✓ Start delay with dependencies parsing")

	# Test start delay with actions
	result = parse("API+2|silent=echo hello")
	assert result.key == "API"
	assert result.start_delay == 2.0
	assert result.actions == ['silent']
	print("✓ Start delay with actions parsing")

	# Test complex format with everything
	result = parse("API#blue+2:DB|silent=echo hello")
	assert result.key == "API"
	assert result.color == "blue"
	assert result.start_delay == 2.0
	assert len(result.dependencies) == 1
	assert result.dependencies[0].key == "DB"
	assert result.actions == ['silent']
	print("✓ Complex format with all features parsing")

	# Test fractional delays
	result = parse("API+1.5=echo hello")
	assert result.start_delay == 1.5
	print("✓ Fractional delay parsing")

	# Test delay with units
	result = parse("API+500ms=echo hello")
	assert result.start_delay == 0.5
	print("✓ Delay with millisecond units parsing")


def test_execution_timing():
	"""Test actual execution timing with start delays"""

	# Test simple delay execution
	runner = Runner()
	start_time = time.time()

	runner.run(['echo', 'immediate'], key="immediate")
	runner.run(['echo', 'delayed'], key="delayed", start_delay=1.0)

	# Both should be started (delayed one in background)
	# Wait for completion
	runner.join(timeout=5)

	elapsed = time.time() - start_time
	assert elapsed >= 1.0, f"Expected at least 1 second delay, got {elapsed}"
	assert elapsed < 2.0, f"Expected less than 2 seconds total, got {elapsed}"
	print("✓ Execution timing with start delays")


def test_delay_error_handling():
	"""Test error handling for invalid delay formats"""

	# Named start conditions wait for another command before starting
	result = parse("API+DB=echo hello")
	assert result.start_delay == 0.0, result
	assert result.start_steps == [Wait("DB", False)], result
	print("✓ Named start condition handling")
# EOF
