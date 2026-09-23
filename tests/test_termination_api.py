"""Module: test_termination_api — tests public command termination."""

from __future__ import annotations

import time

from multiplex import run, terminate


def test_terminate_stops_a_long_running_command() -> None:
	"""`terminate` stops a command started through `run`."""
	command = run("bash", "-c", "while true; do sleep 1; done")
	time.sleep(0.1)

	assert terminate(command)
	assert not command.is_running


# EOF
