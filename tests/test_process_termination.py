"""Module: test_process_termination — tests low-level process termination."""

from __future__ import annotations

import signal
import subprocess

from multiplex import Proc


def test_proc_kill_stops_a_process() -> None:
	"""`Proc.kill` stops a process identified by its PID."""
	process = subprocess.Popen(["sleep", "30"])	 # nosec: B603
	try:
		assert Proc.exists(process.pid)
		assert Proc.kill(process.pid, signal.SIGTERM)
		assert process.wait(timeout=2) == -signal.SIGTERM
	finally:
		if process.poll() is None:
			process.kill()


# EOF
