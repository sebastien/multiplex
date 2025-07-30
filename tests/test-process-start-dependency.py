#!/usr/bin/env python3
"""Test cases for process start dependency functionality.

This tests the actual runtime behavior of the & indicator in dependencies,
ensuring that processes wait for other processes to START rather than END.
"""

import sys
import os
import time
import threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/py'))

from multiplex import Runner, parse

def test_start_dependency_timing():
    """Test that start dependency (:A&) waits for process start, not end"""
    runner = Runner()
    start_times = {}
    
    def record_time(key):
        start_times[key] = time.time()
    
    # Start a long-running process first
    start_times['base'] = time.time()
    cmd_a = runner.run(["sleep", "2"], key="A")
    
    # Small delay to ensure A is definitely started
    time.sleep(0.1)
    
    # Start a process that waits for A to start (:A&)
    # This should start almost immediately since A has already started
    parsed = parse(":A&=echo done")
    cmd_b = runner.run(
        parsed.command,
        key="B", 
        dependencies=parsed.dependencies
    )
    
    # Record when B actually started running its command
    start_times['B'] = time.time()
    
    # Wait for B to complete (should be very quick since it's just echo)
    runner.join(cmd_b, timeout=1.0)
    
    # Calculate timing
    a_start = start_times['base']
    b_start = start_times['B']
    
    # B should start almost immediately after being launched (within 0.5s)
    # If it was waiting for A to END, it would take ~2 seconds
    time_diff = b_start - a_start
    
    print(f"Time from A start to B start: {time_diff:.3f}s")
    
    # Assert that B started quickly (waiting for A's start, not end)
    assert time_diff < 0.5, f"B took too long to start ({time_diff:.3f}s), suggesting it waited for A to end"
    
    # Clean up
    runner.terminate(cmd_a)
    
    print("✓ Start dependency timing works correctly")

def test_start_vs_end_dependency():
    """Test difference between start (:A&) and end (:A) dependencies"""
    runner = Runner()
    
    # Test end dependency first
    start_time = time.time()
    cmd_a = runner.run(["sleep", "1"], key="A")
    
    # Wait for A to end before starting B
    parsed_end = parse(":A=echo end")
    cmd_b_end = runner.run(
        parsed_end.command,
        key="B_END",
        dependencies=parsed_end.dependencies
    )
    
    runner.join(cmd_b_end, timeout=3.0)
    end_dependency_time = time.time() - start_time
    
    # Clean up
    runner.terminate(cmd_a)
    runner.commands.clear()
    runner.process_started.clear()
    
    # Test start dependency
    start_time = time.time()
    cmd_a2 = runner.run(["sleep", "1"], key="A")
    
    # Small delay to ensure A is started
    time.sleep(0.1)
    
    # Wait for A to start before starting B
    parsed_start = parse(":A&=echo start")
    cmd_b_start = runner.run(
        parsed_start.command,
        key="B_START",
        dependencies=parsed_start.dependencies
    )
    
    runner.join(cmd_b_start, timeout=2.0)
    start_dependency_time = time.time() - start_time
    
    print(f"End dependency total time: {end_dependency_time:.3f}s")
    print(f"Start dependency total time: {start_dependency_time:.3f}s")
    
    # Start dependency should be much faster
    assert start_dependency_time < end_dependency_time, "Start dependency should be faster than end dependency"
    assert start_dependency_time < 0.5, f"Start dependency took too long ({start_dependency_time:.3f}s)"
    
    # Clean up
    runner.terminate(cmd_a2)
    
    print("✓ Start vs end dependency difference works correctly")

def test_start_dependency_with_delay():
    """Test start dependency with delay (:A&+1s)"""
    runner = Runner()
    
    start_time = time.time()
    cmd_a = runner.run(["sleep", "2"], key="A")
    
    # Small delay to ensure A is started
    time.sleep(0.1)
    
    # Wait for A to start, then add 1 second delay
    parsed = parse(":A&+1s=echo delayed")
    cmd_b = runner.run(
        parsed.command,
        key="B",
        dependencies=parsed.dependencies
    )
    
    runner.join(cmd_b, timeout=3.0)
    total_time = time.time() - start_time
    
    print(f"Start dependency with 1s delay total time: {total_time:.3f}s")
    
    # Should take about 1.1s (0.1s for A to start + 1s delay)
    assert 1.0 < total_time < 1.5, f"Expected ~1.1s, got {total_time:.3f}s"
    
    # Clean up
    runner.terminate(cmd_a)
    
    print("✓ Start dependency with delay works correctly")

if __name__ == "__main__":
    test_start_dependency_timing()
    test_start_vs_end_dependency() 
    test_start_dependency_with_delay()
    print("All start dependency tests passed!")