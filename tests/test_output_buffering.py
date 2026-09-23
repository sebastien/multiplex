"""Module: test_output_buffering — tests output callback buffering."""

from __future__ import annotations

from multiplex import join, run


def test_output_callback_receives_buffered_stdout() -> None:
	"""A command callback receives stdout before `join` returns."""
	chunks: list[bytes] = []
	command = run("echo", "hello", on_out=lambda _command, data: chunks.append(data))

	join(command)

	assert b"hello" in b"".join(chunks)


# EOF
