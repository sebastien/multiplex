#!/usr/bin/env python3.13
from __future__ import annotations
from collections.abc import Callable, Iterable
from pathlib import Path
from threading import Thread
from typing import NamedTuple, ClassVar
import argparse
import os
import re
import select
import signal
import subprocess
import sys
import time

# --
# # Multiplex
#
# The `multiplex` module implements a multiplexing command runner that allows
# for running multiple, potentially long running commands, merge their output
# a single output stream.


# --
# ## Types

# FROM: https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
# 7-bit and 8-bit C1 ANSI sequences
RE_ANSI_ESCAPE_8BIT = re.compile(
	rb"(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])"
)
RE_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

type BytesConsumer = Callable[[bytes], None]
type StartCallback = Callable[[Command], None]
type OutCallback = Callable[[Command, bytes], None]
type ErrCallback = Callable[[Command, bytes], None]
type EndCallback = Callable[[Command, int], None]
type DataCallback = Callable[[Command, bytes], None]


def SwallowStart(command: Command) -> None:
	pass


def SwallowOut(command: Command, data: bytes) -> None:
	pass


def SwallowErr(command: Command, data: bytes) -> None:
	pass


def SwallowEnd(command: Command, data: int) -> None:
	pass


RE_PID = re.compile(r"(\d+)")

# Platform detection for /proc filesystem availability
_HAS_PROC = Path("/proc").exists()


def shell(command: list[str], input: bytes | None = None) -> bytes | None:
	"""Runs the given command as a subprocess, piping the input, stderr and out"""
	# FROM: https://stackoverflow.com/questions/163542/how-do-i-pass-a-string-into-subprocess-popen-using-the-stdin-argument#165662
	res = subprocess.run(
		command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, input=input
	)
	return res.stdout if res.returncode == 0 else None


class Proc:
	"""An abstraction over the `/proc` filesystem to collect
	information on running processes."""

	@staticmethod
	def children(pid: int) -> set[int]:
		res = set()
		for line in (shell(["ps", "-g", str(pid)]) or b"").split(b"\n"):
			cpid = str(line.split()[0], "utf8") if line else None
			if cpid and RE_PID.match(cpid):
				res.add(int(cpid))
		return res

	@staticmethod
	def parent(pid: int) -> int | None:
		if _HAS_PROC:
			# Linux implementation using /proc
			path = Path(f"/proc/{pid}/stat")
			return int(path.read_text().split()[3]) if path.exists() else None
		else:
			# macOS/BSD fallback using ps
			result = shell(["ps", "-o", "ppid=", "-p", str(pid)])
			if result:
				try:
					return int(result.decode("utf-8").strip())
				except ValueError:
					pass
			return None

	@staticmethod
	def exists(pid: int) -> bool:
		if _HAS_PROC:
			# Linux implementation using /proc
			return Path(f"/proc/{pid}").exists()
		else:
			# macOS/BSD fallback using os.kill with signal 0
			try:
				os.kill(pid, 0)
				return True
			except OSError:
				return False

	@staticmethod
	def kill(pid: int, sig: signal.Signals = signal.SIGHUP) -> bool:
		try:
			os.killpg(pid, sig)
			os.kill(pid, sig)
			os.waitpid(pid, os.WNOHANG)
			return True
		except ProcessLookupError as e:
			if e.errno == 3:  # No such process
				return True
			else:
				return False
		except OSError:
			return False

	@classmethod
	def killchild(cls, pid: int) -> bool:
		return cls.kill(pid)

	@classmethod
	def mem(cls, pid: int) -> tuple[str, str]:
		if _HAS_PROC:
			# Linux implementation using /proc
			try:
				mem = {
					k.strip(): v.strip()
					for k, v in (
						_.split(":", 1)
						for _ in Path(f"/proc/{pid}/status").read_text().split("\n")
						if ":" in _
					)
				}
				# SEE <https://kernelnewbies.kernelnewbies.narkive.com/PG3s6Ndp/ot-meaning-of-proc-pid-status-fields>
				mem_max = mem["VmHWM"]
				mem_all = mem["VmRSS"]
				return mem_all, mem_max
			except (FileNotFoundError, KeyError, IndexError):
				return "0 kB", "0 kB"
		else:
			# macOS/BSD fallback using ps
			result = shell(["ps", "-o", "rss,vsz", "-p", str(pid)])
			if result:
				try:
					lines = result.decode("utf-8").strip().split("\n")
					if len(lines) >= 2:  # Header + data line
						values = lines[1].split()
						if len(values) >= 2:
							# ps outputs memory in KB on macOS
							rss_kb = values[0] + " kB"  # Current RSS memory
							vsz_kb = (
								values[1] + " kB"
							)  # Virtual memory size (approximation for peak)
							return rss_kb, vsz_kb
				except (ValueError, IndexError):
					pass
			return "0 kB", "0 kB"


# def audit(event: str, data: tuple):
#     print(f"Audit: {event} -> {data}")
#
#
# sys.addaudithook(audit)


class Command:
	"""Represents a system command"""

	def __init__(self, args: list[str], key: str, pid: int | None = None) -> None:
		self.key: str = key
		self.args: list[str] = args
		self.pid: int | None = pid
		self._children: set[int] = set()
		# Callbacks
		self.onStart: list[StartCallback | None] = []
		self.onOut: list[OutCallback | None] = []
		self.onErr: list[ErrCallback | None] = []
		self.onEnd: list[EndCallback | None] = []

	# TODO: We may want to have a recursive subprocess listing
	@property
	def children(self) -> set[int]:
		if self.pid:
			self._children = self._children.union(Proc.children(self.pid))
		return self._children

	@property
	def ppid(self) -> int | None:
		return Proc.parent(self.pid) if self.pid else None

	@property
	def isRunning(self) -> bool:
		return bool(
			next(
				(
					_
					for _ in self.children.union(set([self.pid]) if self.pid else set())
					if _ and Proc.exists(_)
				),
				False,
			)
		)

	def silent(self) -> Command:
		if not self.onStart:
			self.onStart.append(SwallowStart)
		if not self.onOut:
			self.onOut.append(SwallowOut)
		if not self.onErr:
			self.onErr.append(SwallowErr)
		if not self.onEnd:
			self.onEnd.append(SwallowEnd)
		return self


# TODO: We could do a CommandRunner that is aprocess, but we would need
# to capture the stdin, stdout, stderr.


class Formatter:
	"""Formats a stream of events coming from a `Runner`."""

	SEP = "│"
	STREAMS = {
		"start": "$",
		"out": "<",
		"err": "!",
		"end": "=",
	}

	def __init__(
		self,
		writer: Callable[[bytes], None] | None = lambda data: None
		if os.write(1, data)
		else None,
	) -> None:
		self.writer = writer

	def start(self, command: Command) -> None:
		return self.format(
			"start", command.key, bytes(" ".join(str(_) for _ in command.args), "utf8")
		)

	def out(self, command: Command, data: bytes) -> None:
		return self.format("out", command.key, data, self.SEP)

	def err(self, command: Command, data: bytes) -> None:
		return self.format("err", command.key, data, self.SEP)

	def end(self, command: Command, data: int) -> None:
		return self.format("end", command.key, data, self.SEP)

	def format(self, stream: str, key: str, data: int | bytes, sep: str = SEP) -> None:
		prefix = bytes(f"{self.STREAMS[stream]}{sep}{key}{sep}", "utf8")
		lines = (
			[bytes(str(data), "utf8")]
			if not isinstance(data, bytes)
			else data.split(b"\n")
		)
		if isinstance(data, bytes) and data.endswith(b"\n"):
			lines = lines[:-1]
		if self.writer:
			for line in lines:
				self.writer(prefix)
				self.writer(line)
				self.writer(b"\n")


# NOTE: This is kind of a stretch, but we want to really say "ThisClass"


# --
# ## Runner
#
# This dispatches the events to the `formatter` first, and then to
# the command's internal event handlers.


class Runner:
	SIGNALS = dict(
		(_, getattr(signal, _).value) for _ in dir(signal) if _.startswith("SIG")
	)
	Instance: ClassVar[Runner | None] = None

	@classmethod
	def Get(cls) -> Runner:
		if cls.Instance is None:
			cls.Instance = Runner()
		return cls.Instance

	def __init__(self) -> None:
		self.commands: dict[str, tuple[Command, Thread]] = {}
		self.formatter: Formatter = Formatter()
		self.registerSignals()

	def getActiveCommands(
		self, commands: dict[str, tuple[Command, Thread]] | None
	) -> dict[str, tuple[Command, Thread]]:
		"""Returns the subset of commands that are active."""
		commands = commands or self.commands
		return dict((k, v) for k, v in commands.items() if v[1].is_alive())

	# --
	# ### Event dispatching
	#
	# This dispatches the events to the `formatter` first, and then to
	# the command's internal event handlers.

	def doStart(self, command: Command) -> None:
		if not command.onStart:
			self.formatter.start(command)
		else:
			for _ in command.onStart:
				if _:
					_(command)

	def doOut(self, command: Command, data: bytes) -> None:
		if not command.onOut:
			self.formatter.out(command, data)
		else:
			for _ in command.onOut:
				if _:
					_(command, data)

	def doErr(self, command: Command, data: bytes) -> None:
		if not command.onErr:
			self.formatter.err(command, data)
		else:
			for _ in command.onErr:
				if _:
					_(command, data)

	def doEnd(self, command: Command, data: int) -> None:
		if not command.onEnd:
			self.formatter.end(command, data)
		else:
			for _ in command.onEnd:
				if _:
					_(command, data)

	# --
	# ### Running, joining, terminating
	#
	# These are the key primitives that
	def _wait_for_process(self, process_key: str) -> None:
		"""Wait for a named process to complete before continuing"""
		if process_key in self.commands:
			cmd, thread = self.commands[process_key]
			# Wait for the thread to complete (which means the process has ended)
			thread.join()

	def run(
		self,
		command: list[str],
		key: str | None = None,
		delay: float | str | None = None,
		actions: list[str] | None = None,
	) -> Command:
		key = key or str(len(self.commands))
		cmd = Command(command, key)
		if actions and "silent" in actions:
			cmd.silent()

		# Handle delays
		if delay is not None:
			if isinstance(delay, (int, float)):
				# Numeric delay: wait specified seconds
				time.sleep(delay)
			elif isinstance(delay, str):
				# Named delay: wait for named process to complete
				self._wait_for_process(delay)

		# NOTE: If the start_new_session attribute is set to true, then
		# all the child processes will belong to the process group with the
		# pid of the command.
		process = subprocess.Popen(
			command,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			bufsize=0,
			start_new_session=True,
		)
		cmd.pid = process.pid

		def onEnd(data: int) -> None:
			self.doEnd(cmd, data)
			if "end" in (actions or ()):
				# NOTE: This is called from the thread, so potentially problematic
				self.terminate()

		# NOTE: We could have just one reader thread that selects, as opposed
		# to having multiple threads that read from each process.
		thread = Thread(
			target=self.reader_threaded,
			args=(
				process,
				lambda data: self.doOut(cmd, data),
				lambda data: self.doErr(cmd, data),
				onEnd,
			),
		)
		thread.start()
		self.commands[key] = (cmd, thread)
		self.doStart(cmd)
		return cmd

	def reader_threaded(
		self,
		process: subprocess.Popen[bytes],
		out: BytesConsumer | None = None,
		err: BytesConsumer | None = None,
		end: Callable[[int], None] | None = None,
	) -> None:
		"""A low-level, streaming blocking reader that calls back `out` and `err` consumers
		upon data."""
		# SEE: https://github.com/python/cpython/blob/3.9/Lib/subprocess.py
		channels = dict(
			(_[0].fileno(), _)
			for _ in ((process.stdout, out), (process.stderr, err))
			if _[0] is not None
		)
		# NOTE: We could simply return the process here and do the multiplexing
		# in the select directly, but the intention is that the `run` command
		# is run in a thread. We use the low-level POSIX APIs in order to
		# do the minimum amount of buffering.
		while waiting := [fd for fd in channels]:
			for fd in select.select(waiting, [], [])[0]:
				chunk = os.read(fd, 64_000)
				if chunk:
					if handler := channels[fd][1]:
						handler(chunk)
				else:
					# NOTE: We were closing the fd there, but really,
					# we shouldn't as we didn't open it ourselves.
					del channels[fd]
		if end:
			end(process.returncode or 0)

	def join(self, *commands: Command, timeout: int | None = None) -> list[Command]:
		"""Joins all or the given list of commands, waiting indefinitely or up
		to the given `timeout` value."""
		selection = (
			dict((k, v) for k, v in self.commands.items() if v[0] in commands)
			if commands
			else self.commands
		)
		started = time.time()
		elapsed: float = 0.0
		poll_timeout = 1.0
		while (active := self.getActiveCommands(selection)) and (
			timeout is None or elapsed < timeout
		):
			# left = timeout - elapsed if timeout else None
			t = (timeout / len(active)) if timeout else None
			t = (
				min(poll_timeout, poll_timeout if t is None else t)
				if poll_timeout
				else t
			)
			for cmd, thread in active.values():
				# Out of courtesy, we wait on the child PID, which is required
				# for the child not be a zombie if it's terminated. I've seen
				# commands in zombie state, but have not isolated yet.
				# --
				# SEE: https://en.wikipedia.org/wiki/Zombie_process
				# «the entry is still needed to allow the parent process to
				# read its child's exit status: once the exit status is read
				# via the wait system call, the zombie's entry is removed from
				# the process table and it is said to be "reaped".»
				if cmd.pid:
					try:
						os.waitpid(cmd.pid, os.WNOHANG)
					except OSError:
						pass
				# We join the thread reader, the thread will end once the channels
				# are closed.
				# TODO: Polling timeout
				# print("TIMEOUT", t)
				thread.join(timeout=t)
			elapsed = time.time() - started
		return [_[0] for _ in self.getActiveCommands(selection).values()]

	def terminate(
		self, *commands: Command, resolution: float = 0.1, timeout: int = 5
	) -> bool:
		"""Terminates given list of commands, waiting indefinitely or up
		to the given `timeout` value."""
		# We extract the commands the corresponding threads
		selection = (
			dict((k, v) for k, v in self.commands.items() if v[0] in commands)
			if commands
			else self.commands
		)
		# Now we iterate and kill, the command processes, the threads will die
		# off accordingly.
		started = time.time()
		iteration = 0
		killed_processes = set()
		while selection:
			for cmd, _ in selection.values():
				all_pids = set([cmd.pid]).union(cmd.children)
				for pid in all_pids:
					if pid is not None and pid not in killed_processes:
						if cmd.pid and Proc.kill(pid):
							killed_processes.add(pid)
			iteration += 1
			# We exit early after the timeout
			elapsed = time.time() - started
			if elapsed >= timeout:
				return False
			# We update the number of active threads
			selection = self.getActiveCommands(selection)
			if selection:
				time.sleep(resolution)
		return True

	# --
	# ### Running, joining, terminating
	#
	# These are the key primitives that

	def registerSignals(self) -> None:
		# Only register for the signals we actually want to handle
		signals_to_handle = ["SIGINT", "SIGTERM"]
		for signame in signals_to_handle:
			if hasattr(signal, signame):
				try:
					sig = getattr(signal, signame)
					signal.signal(sig, self.onSignal)
				except (OSError, ValueError):
					# Signal not available on this platform
					pass

	def onSignal(self, signum: int, frame: object) -> None:
		signame = next((k for k, v in self.SIGNALS.items() if v == signum), None)
		if signame in ("SIGINT", "SIGTERM"):
			print(f"\nReceived {signame}, terminating processes...")
			self.terminate()
			# Wait for processes to actually terminate
			self.join(timeout=2)
			# Exit gracefully after termination
			sys.exit(0)
		elif signame == "SIGCHLD":
			pass


# --
# ##  API


def run(
	*args: str | int,
	onStart: StartCallback | None = None,
	onOut: OutCallback | None = None,
	onErr: ErrCallback | None = None,
	onEnd: EndCallback | None = None,
) -> Command:
	command = Runner.Get().run([str(_) for _ in args])
	if onStart:
		command.onStart.append(onStart)
	if onOut:
		command.onOut.append(onOut)
	if onErr:
		command.onErr.append(onErr)
	if onEnd:
		command.onEnd.append(onEnd)
	return command


def join(*commands: Command, timeout: int | None = None) -> list[Command]:
	return Runner.Get().join(*commands, timeout=timeout)


def terminate() -> bool:
	return Runner.Get().terminate()


def strip_ansi_bytes(data: bytes) -> bytes:
	return RE_ANSI_ESCAPE_8BIT.sub(b"", data)


def strip_ansi(data: str) -> str:
	return RE_ANSI_ESCAPE.sub("", data)


RE_LINE = re.compile(
	r"^((?P<key>[\dA-Za-z_]+)?(\+(?P<delay>\d+(\.\d+)?|[A-Za-z_][\dA-Za-z_]*))?(?P<action>(\|[a-z]+)+)?=)?(?P<command>.+)$"
)


class ParsedCommand(NamedTuple):
	"""Data structure holding a parsed command."""

	key: str
	delay: float | str | None  # Can be numeric delay or named reference
	actions: list[str]
	command: list[str]


def splitargs(command: str) -> Iterable[str]:
	"""Splits the given command line into separate arguments, being mindful of
	quotes."""
	delimiter: str = " "
	SPACE = " "
	ESC = "\\"
	o: int = 0
	p: str = ""
	n: int = len(command)
	for i in range(n):
		c = command[i]
		if c == delimiter and p != ESC:
			if o != i:
				yield command[o:i]
			if c != SPACE:
				delimiter = " "
			o = i + 1
		elif delimiter == SPACE and c in "'\"":
			delimiter = c
			o = i + 1
		p = c
	if o != n:
		yield command[o:]


def parse(line: str) -> ParsedCommand:
	"""Parses a command line"""
	match = RE_LINE.match(line)
	# TODO: Should be a bit more sophisticated
	if not match:
		raise SyntaxError(f"Could not parse command: {line}")
	key = match.group("key")
	delay_str = match.group("delay")
	command = match.group("command")
	actions = (match.group("action") or "").split("|")[1:]

	# Parse delay: can be numeric (float) or named (string)
	delay: float | str | None = None
	if delay_str:
		try:
			delay = float(delay_str)
		except ValueError:
			# It's a named delay (like "A")
			delay = delay_str

	return ParsedCommand(key, delay, actions, [_ for _ in splitargs(command)])


def cli(argv: list[str] | str = sys.argv[1:]) -> None:
	"""The command-line interface of this module."""
	if isinstance(argv, str):
		argv = [argv]
	elif not isinstance(argv, (list, tuple)):
		argv = [str(argv)]
	oparser = argparse.ArgumentParser(
		prog="multiplex",
	)
	# TODO: Rework command lines arguments, we want something that follows
	# common usage patterns.
	oparser.add_argument(
		"commands",
		metavar="COMMANDS",
		type=str,
		nargs="+",
		help="The list of commands to run in parallel",
	)
	oparser.add_argument(
		"-o",
		"--output",
		type=str,
		dest="output",
		default="-",
		help="Specifies an output file",
	)
	oparser.add_argument(
		"-t",
		"--timeout",
		type=float,
		dest="timeout",
		default=0,
		help="Specifies a timeout until which the commands are terminated",
	)
	oparser.add_argument(
		"-p",
		"--parse",
		action="store_true",
		default=False,
		help="Outputs the parsed command",
	)

	# We create the parse and register the options
	args = oparser.parse_args(args=argv)
	out_path = args.output if args.output and args.output != "-" else None
	out = open(out_path, "wt") if out_path else sys.stdout
	if args.parse:
		for command in args.commands:
			key, delay, actions, cmd = parse(command)
			out.write(f"Parsed: {command}\n")
			out.write(f"- key: {key}\n")
			out.write(f"- delay: {delay}\n")
			out.write(f"- actions: {actions}\n")
			out.write(f"- cmd: {cmd}\n")
	else:
		runner = Runner()
		for command in args.commands:
			# FIXME: This is not correct, should take into consideration the \, etc.
			key, delay, actions, cmd = parse(command)
			# FIXME: Delay is not correct, we should sort the commands by delay and
			# do that here instead of from the runner.
			runner.run(cmd, key=key, delay=delay, actions=actions)
		if args.timeout:
			runner.join(timeout=args.timeout)
			runner.terminate()
			runner.join()
		else:
			runner.join()
	if out_path:
		out.close()


if __name__ == "__main__":
	cli()
# EOF
