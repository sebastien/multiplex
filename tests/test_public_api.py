"""Module: test_public_api — tests the public multiplex API."""

from __future__ import annotations

from multiplex import join, run, terminate


def test_run_delivers_output_to_snake_case_callback() -> None:
	"""The public API delivers output through `on_out`."""
	chunks: list[bytes] = []
	command = run("echo", "hello", on_out=lambda _command, data: chunks.append(data))

	assert join(command) == []
	assert b"hello" in b"".join(chunks)
	assert terminate(command)


# EOF
