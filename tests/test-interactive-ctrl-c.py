#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/py'))

from multiplex import run, join

def test_interactive_ctrl_c():
    """Test interactive Ctrl-C handling with a long-running process"""
    print("Starting a long-running process...")
    print("Press Ctrl-C to test signal handling...")
    
    # Start a process that runs for a long time
    cmd = run("sleep", "30")
    print(f"Process {cmd.pid} started. Press Ctrl-C to terminate...")
    
    try:
        # This will block until the process completes or is interrupted
        join(cmd)
        print("Process completed normally")
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt caught! Cleaning up...")
        # The signal handler should have already terminated processes
        if not cmd.isRunning:
            print("✓ Process was properly terminated by signal handler")
        else:
            print("✗ Process is still running after Ctrl-C")
        sys.exit(0)

if __name__ == "__main__":
    test_interactive_ctrl_c()