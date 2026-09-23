"""Module: test_termination_descendants — tests descendant termination."""

from __future__ import annotations

import time
from pathlib import Path

from multiplex import Proc, run, terminate


def test_terminate_stops_command_descendants() -> None:
	"""`terminate` stops the command and its known descendants."""
	script = Path(__file__).with_name("assets") / "forking-process.sh"
	command = run(str(script), on_out=lambda _command, _data: None)
	time.sleep(0.1)
	pids = {command.pid, *command.children} - {None}

	assert terminate(command)
	assert all(not Proc.exists(pid) for pid in pids)


# EOF
