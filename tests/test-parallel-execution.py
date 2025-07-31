#!/usr/bin/env python3
"""
Test parallel execution functionality for multiplex.

This test validates that multiplex actually runs multiple commands in parallel
rather than sequentially, by measuring execution timing.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

# Add src to path to import multiplex
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "py"))

import multiplex


def test_parallel_execution_timing():
    """Test that multiple commands run in parallel, not sequentially"""
    print("Testing parallel execution timing...")
    
    # Test with Python API first
    runner = multiplex.Runner()
    
    start_time = time.time()
    cmd_a = runner.run(["sleep", "1"], key="A")
    cmd_b = runner.run(["sleep", "1"], key="B")
    
    # Wait for both to complete
    runner.join()
    total_time = time.time() - start_time
    
    # If running in parallel, total time should be ~1 second
    # If running sequentially, total time would be ~2 seconds
    print(f"  Python API execution time: {total_time:.2f}s")
    
    # Allow some overhead but should be much closer to 1s than 2s
    assert total_time < 1.5, f"Commands appear to be running sequentially (took {total_time:.2f}s, expected ~1s)"
    assert total_time >= 0.8, f"Commands completed too quickly (took {total_time:.2f}s, expected ~1s)"
    
    print("✓ Python API parallel execution verified")


def test_cli_parallel_execution():
    """Test parallel execution via CLI with timestamp verification"""
    print("Testing CLI parallel execution with timestamps...")
    
    result = subprocess.run([
        sys.executable, "-m", "multiplex", "--timestamp", "-r",
        "A=sh -c 'sleep 1; echo A done'",
        "B=sh -c 'sleep 1; echo B done'"
    ], cwd=Path(__file__).parent.parent / "src" / "py",
       capture_output=True, text=True)
    
    assert result.returncode == 0, f"CLI parallel test failed: {result.stderr}"
    
    lines = result.stdout.strip().split('\n')
    
    # Extract start and completion times
    start_times = []
    completion_times = []
    
    for line in lines:
        if "│A│sh -c" in line or "│B│sh -c" in line:
            # Process start line
            timestamp_match = re.match(r"^(\d{2}):(\d{2}):(\d{2})\|", line)
            if timestamp_match:
                h, m, s = map(int, timestamp_match.groups())
                start_times.append(h * 3600 + m * 60 + s)
        elif ("│A│A done" in line or "│B│B done" in line) and "<│" in line:
            # Process completion line
            timestamp_match = re.match(r"^(\d{2}):(\d{2}):(\d{2})\|", line)
            if timestamp_match:
                h, m, s = map(int, timestamp_match.groups())
                completion_times.append(h * 3600 + m * 60 + s)
    
    # Verify we captured the expected data
    assert len(start_times) == 2, f"Expected 2 start times, got {len(start_times)}: {start_times}"
    assert len(completion_times) == 2, f"Expected 2 completion times, got {len(completion_times)}: {completion_times}"
    
    # Both commands should start at the same time (within 1 second)
    start_time_diff = abs(start_times[0] - start_times[1])
    assert start_time_diff <= 1, f"Commands didn't start simultaneously (diff: {start_time_diff}s)"
    
    # Both commands should complete at roughly the same time (within 1 second)
    completion_time_diff = abs(completion_times[0] - completion_times[1])
    assert completion_time_diff <= 1, f"Commands didn't complete simultaneously (diff: {completion_time_diff}s)"
    
    # Total execution time should be ~1 second, not ~2 seconds
    total_execution_time = max(completion_times) - min(start_times)
    assert total_execution_time <= 2, f"Total execution too long (sequential?): {total_execution_time}s"
    assert total_execution_time >= 1, f"Total execution too short: {total_execution_time}s"
    
    print(f"  Start time difference: {start_time_diff}s")
    print(f"  Completion time difference: {completion_time_diff}s") 
    print(f"  Total execution time: {total_execution_time}s")
    print("✓ CLI parallel execution verified")


def test_multiple_commands_parallel():
	"""Test that more than 2 commands run in parallel"""
	print("Testing multiple commands in parallel...")
	
	# Use a simpler timing test that's less susceptible to output interleaving
	start_time = time.time()
	result = subprocess.run([
		sys.executable, "-m", "multiplex",
		"A=sleep 0.8",
		"B=sleep 0.8", 
		"C=sleep 0.8",
		"D=sleep 0.8"
	], cwd=Path(__file__).parent.parent / "src" / "py",
	   capture_output=True, text=True)
	total_time = time.time() - start_time
	
	assert result.returncode == 0, f"Multiple commands test failed: {result.stderr}"
	
	# If running in parallel, should take ~0.8s
	# If running sequentially, would take ~3.2s
	print(f"  4 commands (0.8s each) execution time: {total_time:.2f}s")
	
	assert total_time < 1.5, f"Commands appear to be running sequentially (took {total_time:.2f}s, expected ~0.8s)"
	assert total_time >= 0.6, f"Commands completed too quickly (took {total_time:.2f}s, expected ~0.8s)"
	
	print("✓ Multiple commands parallel execution verified")

def test_sequential_vs_parallel_timing():
    """Compare sequential vs parallel execution to demonstrate the difference"""
    print("Testing sequential vs parallel timing comparison...")
    
    # Sequential execution using dependencies
    start_time = time.time()
    result_sequential = subprocess.run([
        sys.executable, "-m", "multiplex",
        "A=sh -c 'sleep 0.5; echo A done'",
        "B:A=sh -c 'sleep 0.5; echo B done'"  # B waits for A to complete
    ], cwd=Path(__file__).parent.parent / "src" / "py",
       capture_output=True, text=True)
    sequential_time = time.time() - start_time
    
    # Parallel execution
    start_time = time.time()
    result_parallel = subprocess.run([
        sys.executable, "-m", "multiplex", 
        "A=sh -c 'sleep 0.5; echo A done'",
        "B=sh -c 'sleep 0.5; echo B done'"  # B runs independently
    ], cwd=Path(__file__).parent.parent / "src" / "py",
       capture_output=True, text=True)
    parallel_time = time.time() - start_time
    
    assert result_sequential.returncode == 0, "Sequential test failed"
    assert result_parallel.returncode == 0, "Parallel test failed"
    
    print(f"  Sequential execution time: {sequential_time:.2f}s")
    print(f"  Parallel execution time: {parallel_time:.2f}s")
    
    # Sequential should take roughly twice as long as parallel
    time_ratio = sequential_time / parallel_time
    assert time_ratio > 1.5, f"Sequential should be significantly slower than parallel (ratio: {time_ratio:.2f})"
    
    print(f"  Time ratio (sequential/parallel): {time_ratio:.2f}x")
    print("✓ Sequential vs parallel timing difference confirmed")


def main():
    """Run all parallel execution tests"""
    print("Running parallel execution tests...")
    
    try:
        test_parallel_execution_timing()
        test_cli_parallel_execution()
        test_multiple_commands_parallel()
        test_sequential_vs_parallel_timing()
        print("\n✅ All parallel execution tests passed!")
        return 0
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())