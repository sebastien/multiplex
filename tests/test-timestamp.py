#!/usr/bin/env python3
"""
Test timestamp functionality for multiplex.

This test verifies that the --time and --time=relative options work correctly.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

# Add src to path to import multiplex
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "py"))

import multiplex


def test_timestamp_formatting():
    """Test that timestamps are formatted correctly"""
    print("Testing timestamp formatting...")
    
    # Test absolute timestamp formatting
    formatter = multiplex.Formatter(timestamp=True, relative=False)
    timestamp_prefix = formatter._get_timestamp_prefix()
    
    # Should match HH:MM:SS| format
    timestamp_pattern = re.compile(rb"^\d{2}:\d{2}:\d{2}\|$")
    assert timestamp_pattern.match(timestamp_prefix), f"Absolute timestamp format incorrect: {timestamp_prefix}"
    print("✓ Absolute timestamp format correct")
    
    # Test relative timestamp formatting
    formatter_rel = multiplex.Formatter(timestamp=True, relative=True)
    # Sleep briefly to ensure relative time works
    time.sleep(0.1)
    timestamp_prefix_rel = formatter_rel._get_timestamp_prefix()
    
    # Should match HH:MM:SS| format for relative time
    assert timestamp_pattern.match(timestamp_prefix_rel), f"Relative timestamp format incorrect: {timestamp_prefix_rel}"
    # For relative, it should start with 00:00:00 or very close
    assert timestamp_prefix_rel.startswith(b"00:00:0"), f"Relative timestamp should start near 00:00:00: {timestamp_prefix_rel}"
    print("✓ Relative timestamp format correct")


def test_cli_timestamp_options():
	"""Test CLI with timestamp options"""
	print("Testing CLI timestamp options...")
	
	# Test basic timestamp functionality via CLI
	result = subprocess.run(
		[sys.executable, "-m", "multiplex", "--time", "echo test"],
		cwd=Path(__file__).parent.parent / "src" / "py",
		capture_output=True,
		text=True
	)
	
	# Should succeed
	assert result.returncode == 0, f"CLI failed with timestamp: {result.stderr}"
	
	# Output should contain timestamp prefix
	lines = result.stdout.strip().split('\n')
	timestamp_pattern = re.compile(r"^\d{2}:\d{2}:\d{2}\|\$│\d+│echo test$")
	start_line = next((line for line in lines if "echo test" in line), None)
	assert start_line, f"Start line not found in output: {lines}"
	assert timestamp_pattern.match(start_line), f"Timestamp format incorrect in output: {start_line}"
	print("✓ CLI timestamp option works")
	
	# Test relative timestamp functionality
	result_rel = subprocess.run(
		[sys.executable, "-m", "multiplex", "--time=relative", "echo test"],
		cwd=Path(__file__).parent.parent / "src" / "py",
		capture_output=True,
		text=True
	)
	
	# Should succeed
	assert result_rel.returncode == 0, f"CLI failed with relative timestamp: {result_rel.stderr}"
	
	# Output should contain relative timestamp (starting with 00:00:0)
	lines_rel = result_rel.stdout.strip().split('\n')
	start_line_rel = next((line for line in lines_rel if "echo test" in line), None)
	assert start_line_rel, f"Start line not found in relative output: {lines_rel}"
	assert start_line_rel.startswith("00:00:0"), f"Relative timestamp should start with 00:00:0: {start_line_rel}"
	print("✓ CLI relative timestamp option works")

def test_timestamp_multiple_commands():
	"""Test timestamps with multiple commands"""
	print("Testing timestamps with multiple commands...")
	
	result = subprocess.run([
		sys.executable, "-m", "multiplex", "--time=relative",
		"A=echo hello from A",
		"B+1s=echo hello from B"
	], cwd=Path(__file__).parent.parent / "src" / "py",
	   capture_output=True, text=True)
	
	assert result.returncode == 0, f"Multi-command test failed: {result.stderr}"
	
	lines = result.stdout.strip().split('\n')
	
	# Find A's output - should start near 00:00:00
	a_lines = [line for line in lines if "│A│" in line]
	assert len(a_lines) >= 2, f"Expected at least 2 lines for command A: {a_lines}"
	
	# Find B's output - should start near 00:00:01 due to 1s delay
	b_lines = [line for line in lines if "│B│" in line]
	assert len(b_lines) >= 2, f"Expected at least 2 lines for command B: {b_lines}"
	
	# Check that B starts after A (timestamp should be >= 1 second)
	b_start_line = next((line for line in b_lines if "$│B│" in line), None)
	assert b_start_line, f"B start line not found: {b_lines}"
	
	# Extract timestamp from B's start (should be 00:00:01 or later)
	timestamp_match = re.match(r"^(\d{2}):(\d{2}):(\d{2})\|", b_start_line)
	assert timestamp_match, f"Could not extract timestamp from B start: {b_start_line}"
	
	hours, minutes, seconds = map(int, timestamp_match.groups())
	total_seconds = hours * 3600 + minutes * 60 + seconds
	assert total_seconds >= 1, f"B should start at least 1 second after A: {b_start_line}"
	print("✓ Timestamps work correctly with multiple commands and delays")

def main():
    """Run all timestamp tests"""
    print("Running timestamp tests...")
    
    try:
        test_timestamp_formatting()
        test_cli_timestamp_options()  
        test_timestamp_multiple_commands()
        print("\n✅ All timestamp tests passed!")
        return 0
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())