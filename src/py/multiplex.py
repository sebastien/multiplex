#!/usr/bin/env python3.13
from __future__ import annotations
from collections.abc import Callable, Iterable
from pathlib import Path
from threading import Thread
from typing import NamedTuple, ClassVar
import argparse
import datetime
import os
import re
import select
import signal
import subprocess  # nosec: B404
import sys
import threading
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
	res = subprocess.run(  # nosec: B603
		command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, input=input
	)
	return res.stdout if res.returncode == 0 else None


class Proc:
	"""An abstraction over the `/proc` filesystem to collect
	information on running processes."""

	@staticmethod
	def children(pid: int) -> set[int]:
		res = set()
		# Use process group to find all children (including descendants)
		try:
			if _HAS_PROC:
				# Linux: use /proc to find children more reliably
				for proc_dir in Path("/proc").iterdir():
					if proc_dir.is_dir() and proc_dir.name.isdigit():
						try:
							stat_file = proc_dir / "stat"
							if stat_file.exists():
								stat_content = stat_file.read_text().split()
								if len(stat_content) > 4:
									ppid = int(stat_content[3])
									if ppid == pid:
										res.add(int(proc_dir.name))
						except (ValueError, OSError, IndexError):
							continue
			else:
				# macOS/BSD: use ps to find process group members
				for line in (shell(["ps", "-g", str(pid)]) or b"").split(b"\n"):
					cpid = str(line.split()[0], "utf8") if line else None
					if cpid and RE_PID.match(cpid):
						child_pid = int(cpid)
						if child_pid != pid:  # Don't include the parent itself
							res.add(child_pid)
		except Exception:
			# Fallback to original method if anything fails
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
	def kill(
		pid: int, sig: signal.Signals = signal.SIGTERM, use_group: bool = True
	) -> bool:
		"""Kill a process and optionally its process group"""
		try:
			if use_group:
				# Try to kill the entire process group first
				try:
					os.killpg(pid, sig)
				except ProcessLookupError:
					# Process group doesn't exist, try individual process
					pass
				except OSError:
					# May not have permission to kill group, try individual process
					pass

			# Always try to kill the individual process
			os.kill(pid, sig)

			# Only wait if we're killing (not just signaling)
			if sig in (signal.SIGTERM, signal.SIGKILL):
				try:
					os.waitpid(pid, os.WNOHANG)
				except OSError:
					pass

			return True
		except ProcessLookupError as e:
			if e.errno == 3:  # No such process
				return True
			else:
				return False
		except OSError:
			return False

	@classmethod
	def killchild(cls, pid: int, sig: signal.Signals = signal.SIGTERM) -> bool:
		return cls.kill(pid, sig, use_group=True)

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

	def __init__(
		self,
		args: list[str],
		key: str,
		color: str | None = None,
		pid: int | None = None,
	) -> None:
		self.key: str = key
		self.color: str | None = color
		self.args: list[str] = args
		self.pid: int | None = pid
		self.pgid: int | None = None  # Process group ID
		self._children: set[int] = set()
		self.redirect_stop_event: threading.Event | None = None  # For stopping redirect threads
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

	# ANSI color codes for named colors
	COLORS = {
		"black": "30",
		"red": "31",
		"green": "32",
		"yellow": "33",
		"blue": "34",
		"magenta": "35",
		"cyan": "36",
		"white": "37",
		# NOTE: Maybe define aliases with a shorter syntax
		"bright_black": "90",
		"bright_red": "91",
		"bright_green": "92",
		"bright_yellow": "93",
		"bright_blue": "94",
		"bright_magenta": "95",
		"bright_cyan": "96",
		"bright_white": "97",
	}

	def __init__(
		self,
		writer: Callable[[bytes], None] | None = lambda data: None
		if os.write(1, data)
		else None,
		timestamp: bool = False,
		relative: bool = False,
	) -> None:
		self.writer = writer
		self.timestamp = timestamp
		self.relative = relative
		self.start_time = datetime.datetime.now() if timestamp else None

	def _get_timestamp_prefix(self) -> bytes:
		"""Generate timestamp prefix for log entries"""
		if not self.timestamp or not self.start_time:
			return b""
		
		current_time = datetime.datetime.now()
		if self.relative:
			# Calculate time relative to start
			elapsed = current_time - self.start_time
			total_seconds = int(elapsed.total_seconds())
			hours = total_seconds // 3600
			minutes = (total_seconds % 3600) // 60
			seconds = total_seconds % 60
			timestamp_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
		else:
			# Use current time
			timestamp_str = current_time.strftime("%H:%M:%S")
		
		return bytes(f"{timestamp_str}|", "utf8")

	def _get_color_code(self, color: str | None) -> str:
		"""Convert color name or hex code to ANSI escape sequence"""
		if not color:
			return ""

		color_lower = color.lower()

		# Check if it's a named color
		if color_lower in self.COLORS:
			return f"\033[{self.COLORS[color_lower]}m"

		# Check if it's a hex color (6 digits)
		if len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color):
			# Convert hex to RGB
			r = int(color[0:2], 16)
			g = int(color[2:4], 16)
			b = int(color[4:6], 16)
			return f"\033[38;2;{r};{g};{b}m"

		# Invalid color, return empty string
		return ""

	def _apply_color(self, text: str, color: str | None) -> bytes:
		"""Apply color to text and return as bytes"""
		if not color:
			return bytes(text, "utf8")

		color_code = self._get_color_code(color)
		if color_code:
			reset_code = "\033[0m"
			return bytes(f"{color_code}{text}{reset_code}", "utf8")

		return bytes(text, "utf8")

	def start(self, command: Command) -> None:
		return self.format(
			"start",
			command.key,
			bytes(" ".join(str(_) for _ in command.args), "utf8"),
			color=command.color,
		)

	def out(self, command: Command, data: bytes) -> None:
		return self.format("out", command.key, data, self.SEP, command.color)

	def err(self, command: Command, data: bytes) -> None:
		return self.format("err", command.key, data, self.SEP, command.color)

	def end(self, command: Command, data: int) -> None:
		return self.format("end", command.key, data, self.SEP, command.color)

	def format(
		self,
		stream: str,
		key: str,
		data: int | bytes,
		sep: str = SEP,
		color: str | None = None,
	) -> None:
		timestamp_prefix = self._get_timestamp_prefix()
		colored_key = self._apply_color(key, color)
		stream_prefix = bytes(f"{self.STREAMS[stream]}{sep}", "utf8")
		sep_suffix = bytes(f"{sep}", "utf8")
		lines = (
			[bytes(str(data), "utf8")]
			if not isinstance(data, bytes)
			else data.split(b"\n")
		)
		if isinstance(data, bytes) and data.endswith(b"\n"):
			lines = lines[:-1]
		if self.writer:
			for line in lines:
				self.writer(timestamp_prefix)
				self.writer(stream_prefix)
				self.writer(colored_key)
				self.writer(sep_suffix)
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

	def __init__(self, timestamp: bool = False, relative: bool = False) -> None:
		self.commands: dict[str, tuple[Command, Thread]] = {}
		self.process_started: dict[
			str, threading.Event
		] = {}  # Track process start events
		self.process_outputs: dict[
			str, dict[int, list[bytes]]
		] = {}  # Track process outputs by key and stream
		self.formatter: Formatter = Formatter(timestamp=timestamp, relative=relative)
		self.graceful_timeout: float = 5.0  # Default graceful shutdown timeout
		self.force_timeout: float = 2.0  # Additional time before SIGKILL
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
		# Signal redirect threads to stop for this command
		if hasattr(command, 'redirect_stop_event') and command.redirect_stop_event:
			command.redirect_stop_event.set()
		
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
	def _waitForProcess(self, proc: str, *, delay: int | None = None) -> None:
		"""Wait for a named process to complete before continuing"""
		if proc in self.commands:
			_, thread = self.commands[proc]
			# Wait for the thread to complete (which means the process has ended)
			thread.join()
			if delay:
				time.sleep(delay)

	def _waitForProcessStart(self, proc: str) -> None:
		"""Wait for a named process to start before continuing"""
		if proc in self.process_started:
			event = self.process_started[proc]
			# Wait for the event to be set (which means the process has started)
			event.wait()

	def _waitForEvent(self, event: str, *, delay: int | None = None) -> None:
		raise NotImplementedError

	def run(
		self,
		command: list[str],
		key: str | None = None,
		color: str | None = None,
		start_delay: float = 0.0,
		dependencies: list[Dependency] | None = None,
		redirects: Redirect | None = None,
		actions: list[str] | None = None,
	) -> Command:
		key = key or str(len(self.commands))
		cmd = Command(command, key, color)
		if actions and "silent" in actions:
			cmd.silent()

		# Create a start event for this process
		self.process_started[key] = threading.Event()

		# Initialize output tracking for this process
		self.process_outputs[key] = {1: [], 2: []}  # stdout and stderr buffers

		# Handle redirects - create stdin pipe if needed
		stdin_pipe = None
		if redirects:
			# Create a pipe for stdin
			stdin_read_fd, stdin_write_fd = os.pipe()
			stdin_pipe = stdin_read_fd

			# Create a stop event for the redirect manager
			redirect_stop_event = threading.Event()

			# Start a thread to manage the redirect data flow
			def redirect_manager() -> None:
				try:
					while not redirect_stop_event.is_set():
						# Collect data from all redirect sources
						for source in redirects.sources:
							if source.key in self.process_outputs:
								output_buffer = self.process_outputs[source.key][
									source.stream
								]
								if output_buffer:
									# Write all buffered data to stdin pipe
									data = b"".join(output_buffer)
									output_buffer.clear()
									if data:
										try:
											os.write(stdin_write_fd, data)
										except (OSError, BrokenPipeError):
											# Pipe closed, stop redirecting
											return

						# Small delay to avoid busy waiting
						time.sleep(0.001)
				except (OSError, BrokenPipeError):
					# Process has ended or pipe closed
					pass
				finally:
					try:
						os.close(stdin_write_fd)
					except OSError:
						pass

			# Start the redirect manager thread
			redirect_thread = threading.Thread(target=redirect_manager, daemon=True)
			redirect_thread.start()

			# Store the stop event so we can signal it when this command ends
			cmd.redirect_stop_event = redirect_stop_event

		# Handle dependencies
		if dependencies:
			for dep in dependencies:
				if dep.wait_for_start:
					# Wait for process to start
					self._waitForProcessStart(dep.key)
				else:
					# Wait for process to end
					self._waitForProcess(dep.key)

				# Apply any delays after dependency
				for delay in dep.delays:
					time.sleep(delay)

		# Apply start delay
		if start_delay > 0:
			time.sleep(start_delay)

		# NOTE: If the start_new_session attribute is set to true, then
		# all the child processes will belong to the process group with the
		# pid of the command.
		process = subprocess.Popen(  # nosec: B603
			command,
			stdin=stdin_pipe,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			bufsize=0,
			start_new_session=True,
		)
		cmd.pid = process.pid
		cmd.pgid = process.pid  # With start_new_session=True, pgid equals pid

		# Signal that the process has started
		self.process_started[key].set()

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
				key,  # Pass the key for output capture
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
		capture_key: str | None = None,
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
					# Capture output for redirects if requested
					if capture_key and capture_key in self.process_outputs:
						# Determine which stream this is (stdout=1, stderr=2)
						if process.stdout and fd == process.stdout.fileno():
							self.process_outputs[capture_key][1].append(chunk)
						elif process.stderr and fd == process.stderr.fileno():
							self.process_outputs[capture_key][2].append(chunk)

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
		self, *commands: Command, graceful: bool = True, timeout: int | None = None
	) -> bool:
		"""Terminates given list of commands with optional graceful shutdown.

		Args:
			*commands: Specific commands to terminate, or all if none specified
			graceful: If True, try SIGTERM first, then SIGKILL after timeout
			timeout: Override default timeout for graceful shutdown

		Returns:
			True if all processes terminated successfully, False otherwise
		"""
		# Use provided timeout or defaults
		grace_timeout = timeout or self.graceful_timeout
		force_timeout = self.force_timeout

		# We extract the commands and corresponding threads
		selection = (
			dict((k, v) for k, v in self.commands.items() if v[0] in commands)
			if commands
			else self.commands
		)

		if not selection:
			return True

		# Phase 1: Graceful termination with SIGTERM
		if graceful:
			started = time.time()
			killed_processes = set()

			# Send SIGTERM to all processes
			for cmd, _ in selection.values():
				all_pids = set([cmd.pid]).union(cmd.children)
				for pid in all_pids:
					if pid is not None and pid not in killed_processes:
						if Proc.exists(pid) and Proc.kill(
							pid, signal.SIGTERM, use_group=True
						):
							killed_processes.add(pid)

			# Wait for graceful shutdown
			while selection and (time.time() - started) < grace_timeout:
				selection = self.getActiveCommands(selection)
				if selection:
					time.sleep(0.1)  # Small sleep to avoid busy waiting

			# If all processes terminated gracefully, we're done
			if not selection:
				return True

		# Phase 2: Force termination with SIGKILL
		started = time.time()
		iteration = 0
		killed_processes = set()

		while selection:
			for cmd, _ in selection.values():
				all_pids = set([cmd.pid]).union(cmd.children)
				for pid in all_pids:
					if pid is not None and pid not in killed_processes:
						if Proc.exists(pid) and Proc.kill(
							pid, signal.SIGKILL, use_group=True
						):
							killed_processes.add(pid)

			iteration += 1
			# We exit after the force timeout
			elapsed = time.time() - started
			if elapsed >= force_timeout:
				return False

			# Update the number of active threads
			selection = self.getActiveCommands(selection)
			if selection:
				time.sleep(0.1)

		return True

	# --
	# ### Running, joining, terminating
	#
	# These are the key primitives that

	def registerSignals(self) -> None:
		# Register for signals we want to handle gracefully
		signals_to_handle = ["SIGINT", "SIGTERM", "SIGHUP"]
		for signame in signals_to_handle:
			if hasattr(signal, signame):
				try:
					sig = getattr(signal, signame)
					signal.signal(sig, self.onSignal)
				except (OSError, ValueError):
					# Signal not available on this platform
					pass

	def propagateSignal(self, signum: int) -> None:
		"""Propagate the received signal to all child processes"""
		active_commands = self.getActiveCommands(None)
		if not active_commands:
			return

		for cmd, _ in active_commands.values():
			if cmd.pid:
				# Get all child processes
				all_pids = set([cmd.pid]).union(cmd.children)
				for pid in all_pids:
					if pid and Proc.exists(pid):
						try:
							# Send the same signal that multiplex received
							Proc.kill(pid, signal.Signals(signum), use_group=True)
						except (OSError, ValueError):
							# Process might have already died or signal not valid
							pass

	def onSignal(self, signum: int, frame: object) -> None:
		signame = next((k for k, v in self.SIGNALS.items() if v == signum), None)
		if signame in ("SIGINT", "SIGTERM", "SIGHUP"):
			print(f"\nReceived {signame}, gracefully shutting down processes...")

			# First, propagate the signal to children
			self.propagateSignal(signum)

			# Then attempt graceful termination
			if not self.terminate(graceful=True):
				print("Graceful shutdown failed, forcing termination...")
				self.terminate(graceful=False)

			# Wait for processes to actually terminate
			remaining = self.join(timeout=int(self.force_timeout))
			if remaining:
				print(f"Warning: {len(remaining)} processes did not terminate cleanly")

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


def terminate(*commands: Command, graceful: bool = True) -> bool:
	"""Terminate commands with optional graceful shutdown"""
	return Runner.Get().terminate(*commands, graceful=graceful)


def strip_ansi_bytes(data: bytes) -> bytes:
	return RE_ANSI_ESCAPE_8BIT.sub(b"", data)


def strip_ansi(data: str) -> str:
	return RE_ANSI_ESCAPE.sub("", data)


RE_LINE = re.compile(
	r"^((?P<key>[\dA-Za-z_]+)?(#(?P<color>[A-Fa-f0-9]{6}|[A-Za-z]+))?(?P<start_delay>\+[^:=|<]+?)?(?P<redirects><[^:=|]+?)?(?P<deps>:[^|=]+?)?(?P<action>(\|[a-z]+)+)?=)?(?P<command>.+)$"
)


class Dependency(NamedTuple):
	"""Data structure holding a parsed dependency."""

	key: str  # Process name to wait for
	wait_for_start: bool  # True if waiting for start (&), False for end
	delays: list[float]  # List of delays to apply after dependency


class RedirectSource(NamedTuple):
	"""Data structure holding a single redirect source."""

	key: str  # Process name to redirect from
	stream: int  # Stream number: 1=stdout, 2=stderr


class Redirect(NamedTuple):
	"""Data structure holding a parsed stdin redirect."""

	sources: list[RedirectSource]  # List of sources to combine for stdin


class ParsedCommand(NamedTuple):
	"""Data structure holding a parsed command."""

	key: str
	color: str | None
	start_delay: float  # Delay before starting this command
	dependencies: list[Dependency]  # List of dependencies to wait for
	redirects: Redirect | None  # Stdin redirect configuration
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


def parse_redirects(redirects_str: str) -> Redirect | None:
	"""Parse redirect string into Redirect object.

	Redirects are in the format: <SOURCE... where SOURCE can be:
	- A - stdout from process A
	- 2A - stderr from process A
	- (1A,2A) - stdout and stderr from process A combined
	- (A,B) - stdout from processes A and B combined

	Examples:
	- "<A" - stdin from A's stdout
	- "<2A" - stdin from A's stderr
	- "<(1A,2A)" - stdin from A's stdout and stderr combined
	- "<(A,B)" - stdin from A's and B's stdout combined
	"""
	if not redirects_str or not redirects_str.startswith("<"):
		return None

	# Remove leading '<'
	sources_str = redirects_str[1:]

	sources = []

	# Handle parentheses format: (1A,2A) or (A,B)
	if sources_str.startswith("(") and sources_str.endswith(")"):
		# Remove parentheses and split by commas
		inner = sources_str[1:-1]
		source_parts = [s.strip() for s in inner.split(",")]

		for source_part in source_parts:
			if not source_part:
				continue

			# Check if it starts with a stream number
			if source_part.startswith("1"):
				# 1A format - explicit stdout
				key = source_part[1:]
				stream = 1
			elif source_part.startswith("2"):
				# 2A format - stderr
				key = source_part[1:]
				stream = 2
			else:
				# A format - default to stdout
				key = source_part
				stream = 1

			if key:
				sources.append(RedirectSource(key, stream))

	else:
		# Simple format: A, 2A, 1A
		if sources_str.startswith("2"):
			# 2A format - stderr
			key = sources_str[1:]
			stream = 2
		elif sources_str.startswith("1"):
			# 1A format - explicit stdout
			key = sources_str[1:]
			stream = 1
		else:
			# A format - default to stdout
			key = sources_str
			stream = 1

		if key:
			sources.append(RedirectSource(key, stream))

	if sources:
		return Redirect(sources)

	return None


def parse_dependencies(deps_str: str) -> list[Dependency]:
	"""Parse dependency string into list of Dependency objects.

	Dependencies are in the format: :KEY[&][+DELAY...]:KEY2[&][+DELAY...]...

	Examples:
	- ":A" - wait for process A to end
	- ":A&" - wait for process A to start
	- ":A+1s" - wait for process A to end, then wait 1 second
	- ":A&+500ms" - wait for process A to start, then wait 500ms
	- ":A+1s+500ms" - wait for process A to end, then wait 1.5 seconds total
	- ":A:B&+2s" - wait for A to end, and wait for B to start then 2s
	"""
	if not deps_str or not deps_str.startswith(":"):
		return []

	# Remove leading colon and split by colons to get individual dependencies
	deps_str = deps_str[1:]  # Remove leading ':'
	dep_parts = deps_str.split(":")

	dependencies = []
	for dep_part in dep_parts:
		if not dep_part.strip():
			continue

		# Check for & (wait for start)
		wait_for_start = False
		if "&" in dep_part:
			parts = dep_part.split("&", 1)
			key = parts[0]
			wait_for_start = True
			delay_part = parts[1] if len(parts) > 1 else ""
		else:
			# Split by + to separate key from delays
			plus_pos = dep_part.find("+")
			if plus_pos != -1:
				key = dep_part[:plus_pos]
				delay_part = dep_part[plus_pos:]
			else:
				key = dep_part
				delay_part = ""

		# Parse delays
		delays = []
		if delay_part:
			# Split by + and parse each delay
			delay_strs = [d for d in delay_part.split("+") if d.strip()]
			for delay_str in delay_strs:
				try:
					parsed_delay = parse_delay(delay_str)
					if isinstance(parsed_delay, (int, float)):
						delays.append(float(parsed_delay))
				except ValueError:  # nosec B110
					# Skip invalid delays
					pass

		if key.strip():
			dependencies.append(Dependency(key.strip(), wait_for_start, delays))

	return dependencies


RE_DELAY = re.compile(
	r"^(?:(?P<minutes>\d+(?:\.\d+)?)m)?(?:(?P<seconds>\d+(?:\.\d+)?)s)?(?:(?P<milliseconds>\d+(?:\.\d+)?)ms)?$|^(?P<default>\d+(?:\.\d*)?)$"
)


def parse_delay(delay_str: str) -> float | str:
	"""Parse a delay string with optional time suffixes.

	Supported formats:
	- Plain number: "5", "1.5", "1.0"
	- Milliseconds: "500ms", "1000ms"
	- Seconds: "5s", "1.5s"
	- Minutes: "1m", "2.5m"
	- Complex combinations: "1m30s", "1m1s1ms", "2m15s500ms"
	- Named delay: "A", "server"

	Returns delay in seconds as float, or the original string for named delays.
	"""
	delay_str = delay_str.strip()

	# Try to match the new regex pattern
	match = re.match(RE_DELAY, delay_str)
	if match:
		# Check if it's a default number (plain numeric value)
		default = match.group("default")
		if default:
			return float(default)

		# Parse time components
		total_seconds = 0.0

		# Minutes
		minutes = match.group("minutes")
		if minutes:
			total_seconds += float(minutes) * 60.0

		# Seconds
		seconds = match.group("seconds")
		if seconds:
			total_seconds += float(seconds)

		# Milliseconds
		milliseconds = match.group("milliseconds")
		if milliseconds:
			total_seconds += float(milliseconds) / 1000.0

		return total_seconds

	# If regex doesn't match, try parsing as named delay
	try:
		# Final fallback: try parsing as plain number
		return float(delay_str)
	except ValueError:
		# It's a named delay (like "A" or "server")
		return delay_str


def parse(line: str) -> ParsedCommand:
	"""Parses a command line with the new delay and dependency-based format.

	Format: [KEY][#COLOR][+DELAY…][:DEP…][|ACTION…]=COMMAND
	Where DEP is: [KEY][&][+DELAY…]
	Where REDIRECT is: <A, <2A, <(1A,2A), <(A,B), etc.
	"""
	match = RE_LINE.match(line)
	if not match:
		raise SyntaxError(f"Could not parse command: {line}")

	key = match.group("key")
	color = match.group("color")
	start_delay_str = match.group("start_delay")
	redirects_str = match.group("redirects")
	deps_str = match.group("deps")
	command = match.group("command")
	actions = (match.group("action") or "").split("|")[1:]

	# Parse start delay
	start_delay = 0.0
	if start_delay_str:
		# Remove the '+' prefix and parse
		delay_value = parse_delay(start_delay_str[1:])
		if isinstance(delay_value, str):
			raise SyntaxError(f"Start delay must be a time value, not a named delay: {start_delay_str}")
		start_delay = delay_value

	# Parse redirects
	redirects = parse_redirects(redirects_str or "")

	# Parse dependencies
	dependencies = parse_dependencies(deps_str or "")

	return ParsedCommand(
		key, color, start_delay, dependencies, redirects, actions, [_ for _ in splitargs(command)]
	)


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
	def custom_parse_time_arg(argv):
		"""Custom parser to handle --time and --time=relative properly"""
		time_mode = None
		filtered_argv = []
		i = 0
		while i < len(argv):
			arg = argv[i]
			if arg == "--time":
				# --time without value - default to absolute
				time_mode = "absolute"
			elif arg.startswith("--time="):
				# --time=value format
				value = arg.split("=", 1)[1]
				if value in ("relative", "absolute"):
					time_mode = value
				else:
					raise ValueError(f"Invalid time mode: {value}")
			else:
				filtered_argv.append(arg)
			i += 1
		return filtered_argv, time_mode

	# Custom parse the time argument first
	filtered_argv, time_mode = custom_parse_time_arg(argv)
	
	# Create a mutually exclusive group for time options
	time_group = oparser.add_mutually_exclusive_group()
	time_group.add_argument(
		"--time",
		action="store_const",
		const="absolute",
		dest="time_mode",
		help="Add timestamps to log entries as (HH:MM:SS). Also supports --time=relative for relative timestamps",
	)
	time_group.add_argument(
		"--time-relative",
		action="store_const", 
		const="relative",
		dest="time_mode",
		help="Add relative timestamps (00:00:00 start)",
	)

	# We create the parse and register the options
	args = oparser.parse_args(args=filtered_argv)
	
	# Override time_mode with our custom parsed value if it was found
	if time_mode is not None:
		args.time_mode = time_mode
	out_path = args.output if args.output and args.output != "-" else None
	out = open(out_path, "wt") if out_path else sys.stdout
	if args.parse:
		for command in args.commands:
			parsed_cmd = parse(command)
			out.write(f"Parsed: {command}\n")
			out.write(f"- key: {parsed_cmd.key}\n")
			out.write(f"- color: {parsed_cmd.color}\n")
			out.write(f"- start_delay: {parsed_cmd.start_delay}\n")
			out.write(f"- dependencies: {parsed_cmd.dependencies}\n")
			out.write(f"- redirects: {parsed_cmd.redirects}\n")
			out.write(f"- actions: {parsed_cmd.actions}\n")
			out.write(f"- cmd: {parsed_cmd.command}\n")
	else:
		# Determine timestamp settings from --time argument
		timestamp_enabled = args.time_mode is not None
		relative_timestamps = args.time_mode == "relative"
		
		runner = Runner(timestamp=timestamp_enabled, relative=relative_timestamps)
		for command in args.commands:
			# Parse the command using the new format
			parsed_cmd = parse(command)
			# FIXME: Dependencies should be sorted and handled properly
			runner.run(
				parsed_cmd.command,
				key=parsed_cmd.key,
				color=parsed_cmd.color,
				start_delay=parsed_cmd.start_delay,
				dependencies=parsed_cmd.dependencies,
				redirects=parsed_cmd.redirects,
				actions=parsed_cmd.actions,
			)
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
