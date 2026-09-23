"""Module: conftest — shared pytest lifecycle fixtures."""

from __future__ import annotations

import signal

import pytest
from multiplex import Runner


@pytest.fixture(autouse=True)
def reset_default_runner() -> None:
	"""Restores process signal handlers and releases the shared runner."""
	handlers = {
		signum: signal.getsignal(signum)
		for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
	}
	yield
	if Runner.INSTANCE is not None:
		Runner.INSTANCE.terminate(graceful=False)
		Runner.INSTANCE = None
	for signum, handler in handlers.items():
		signal.signal(signum, handler)


# EOF
