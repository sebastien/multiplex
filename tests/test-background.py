#!/usr/bin/env python3
"""Integration tests for filesystem-backed detached runs."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).parent.parent
MULTIPLEX = ROOT / "src" / "py" / "multiplex.py"


def invoke(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
	return subprocess.run(
		[sys.executable, str(MULTIPLEX), *args],
		cwd=directory,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		check=False,
	)


def wait_for(path: Path, text: str, timeout: float = 3.0) -> None:
	deadline = time.monotonic() + timeout
	while time.monotonic() < deadline:
		if path.exists() and text in path.read_text():
			return
		time.sleep(0.03)
	raise AssertionError(f"{path} did not contain {text!r}")


def test_detached_run_can_be_inspected_tailed_stopped_and_pruned() -> None:
	with tempfile.TemporaryDirectory() as temporary:
		directory = Path(temporary)
		started = invoke(
			directory,
			"start",
			"--prune-after",
			"0.2",
			"dev",
			"APP=python3 -c 'import time; print(\"ready\", flush=True); time.sleep(30)'",
		)
		assert started.returncode == 0, started.stderr
		log = directory / ".multiplex" / "dev" / "output.log"
		wait_for(log, "ready")

		status = invoke(directory, "status")
		assert "dev\trunning" in status.stdout
		tailed = invoke(directory, "tail", "dev")
		assert "ready" in tailed.stdout
		replaced = invoke(
			directory,
			"start",
			"--replace",
			"--prune-after",
			"0.2",
			"dev",
			"APP=python3 -c 'import time; print(\"replaced\", flush=True); time.sleep(30)'",
		)
		assert replaced.returncode == 0, replaced.stderr
		wait_for(log, "replaced")
		assert "replaced" in invoke(directory, "tail", "dev").stdout

		stopped = invoke(directory, "stop", "dev")
		assert stopped.returncode == 0, stopped.stderr
		deadline = time.monotonic() + 3.0
		while (directory / ".multiplex" / "dev").exists() and time.monotonic() < deadline:
			time.sleep(0.03)
		assert not (directory / ".multiplex" / "dev").exists()


if __name__ == "__main__":
	test_detached_run_can_be_inspected_tailed_stopped_and_pruned()
