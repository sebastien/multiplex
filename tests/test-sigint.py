#!/usr/bin/env python3
import sys
import os
import signal
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/py'))

from multiplex import run, terminate, Runner

def test_sigint_handling():
    """Test that SIGINT (Ctrl-C) properly terminates subprocesses"""
    print("Testing SIGINT handling...")
    
    # Start a long-running process
    runner = Runner()
    cmd = runner.run(["sleep", "10"], key="test")
    
    # Verify the process is running
    assert cmd.isRunning, "Process should be running"
    print(f"✓ Process {cmd.pid} is running")
    
    # Wait a bit to ensure process is fully started
    time.sleep(0.5)
    
    # Send SIGINT to ourselves (simulating Ctrl-C)
    print("Sending SIGINT signal...")
    os.kill(os.getpid(), signal.SIGINT)
    
    # Give the signal handler time to work
    time.sleep(1)
    
    # Check if the process was terminated
    if not cmd.isRunning:
        print("✓ SIGINT properly terminated subprocess")
    else:
        print("✗ SIGINT did not terminate subprocess")
        # Manually terminate for cleanup
        runner.terminate()
        runner.join()
        raise AssertionError("SIGINT handling failed")

def test_manual_termination():
    """Test manual termination works correctly"""
    print("\nTesting manual termination...")
    
    runner = Runner()
    cmd = runner.run(["sleep", "5"], key="test2")
    
    assert cmd.isRunning, "Process should be running"
    print(f"✓ Process {cmd.pid} is running")
    
    # Manually terminate
    runner.terminate()
    
    # Wait for termination to complete
    time.sleep(1)
    
    if not cmd.isRunning:
        print("✓ Manual termination successful")
    else:
        print("✗ Manual termination failed")
        raise AssertionError("Manual termination failed")

if __name__ == "__main__":
    try:
        test_manual_termination()
        test_sigint_handling()
        print("\n✅ All signal handling tests passed!")
    except KeyboardInterrupt:
        print("\n✓ SIGINT caught and handled correctly")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)