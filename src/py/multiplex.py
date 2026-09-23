#!/usr/bin/env python3
"""Module: multiplex — runs commands in parallel and merges their output.

Multiplex starts multiple, potentially long-running commands, merges their
stdout and stderr into a single stream, and coordinates their lifecycle through
delays, dependencies, redirects and start-on-output conditions.

It exposes a command-line interface (`cli`) and a small Python API built around
the top-level `run`, `join` and `terminate` functions.
"""

from __future__ import annotations

import argparse
import datetime
import errno
import json
import os
import re
import select
import shutil
import signal
import subprocess  # nosec: B404
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import ClassVar, NamedTuple, TextIO

# -----------------------------------------------------------------------------
#
# DEFINITIONS
#
# -----------------------------------------------------------------------------

# NOTE: Types first

# Type: BytesConsumer
# Consumes a raw chunk of bytes.
type BytesConsumer = Callable[[bytes], None]

# Type: StartCallback
# Notified when a command starts.
type StartCallback = Callable[[Command], None]

# Type: OutCallback
# Notified with a chunk of a command's stdout.
type OutCallback = Callable[[Command, bytes], None]

# Type: ErrCallback
# Notified with a chunk of a command's stderr.
type ErrCallback = Callable[[Command, bytes], None]

# Type: EndCallback
# Notified with a command's exit code.
type EndCallback = Callable[[Command, int], None]

# Data class: Wait
# Waits for the command `key` to start (when `start`) or to end.
class Wait(NamedTuple):
	"""Waits for a command to start or finish."""

	key: str
	start: bool = False


# Data class: InputGuard
# Waits for the guard `name` to match multiplex's standard input.
class InputGuard(NamedTuple):
	"""Waits for a named guard to match standard input."""

	name: str


# Data class: ProcessGuard
# Waits for the guard `name` to match `key`'s output on `streams`.
class ProcessGuard(NamedTuple):
	"""Waits for a named guard to match a command stream."""

	key: str
	streams: tuple[int, ...]
	name: str


# Type: Delay
# A step of a delay chain: a duration, a command wait or a guard wait.
type Delay = float | Wait | InputGuard | ProcessGuard


# Data class: Dependency
# A parsed dependency, waiting for `key` to start or end before applying `delays`.
class Dependency(NamedTuple):
	"""Describes a command dependency and its delay steps."""

	key: str
	wait_for_start: bool
	delays: list[Delay]


# Data class: StreamSource
# A single stdout/stderr source, used by redirects and start-on-output.
class StreamSource(NamedTuple):
	"""Identifies one command output stream."""

	key: str
	stream: int


# Data class: RedirectSource
# Readability alias of `StreamSource` in redirect contexts.
RedirectSource = StreamSource


# Data class: Redirect
# A parsed stdin redirect, combining one or more sources.
class Redirect(NamedTuple):
	"""Combines output streams as a command standard-input redirect."""

	sources: list[StreamSource]


# Data class: StartOnOutputSource
# Readability alias of `StreamSource` in start-on-output contexts.
StartOnOutputSource = StreamSource


# Data class: StartOnOutput
# A parsed start-on-output condition, watching one or more sources.
class StartOnOutput(NamedTuple):
	"""Delays a command until one of its sources emits output."""

	sources: list[StreamSource]


# Data class: ParsedCommand
# A fully parsed command line.
class ParsedCommand(NamedTuple):
	"""Represents one fully parsed command-line declaration."""

	key: str | None
	color: str | None
	start_delay: float
	dependencies: list[Dependency]
	redirects: Redirect | None
	start_on_output: StartOnOutput | None
	actions: list[str]
	command: list[str]
	# Pre-start steps when the start chain contains waits or guards; `start_delay`
	# then only carries a chain that is made purely of durations.
	start_steps: list[Delay] = []  # noqa: RUF012 - NamedTuple field default


# NOTE: Then constants

# Stream numbers as exposed by `subprocess` and `select`.
STDOUT = 1
STDERR = 2

# Run lifecycle states persisted in `state.json`.
STATUS_STARTING = "starting"
STATUS_RUNNING = "running"
STATUS_STOPPED = "stopped"
STATUS_FAILED = "failed"

# Defaults for detached runs.
DEFAULT_STATE_DIR = ".multiplex"
DEFAULT_PRUNE_AFTER = 10.0
DEFAULT_GRACEFUL_TIMEOUT = 5.0
DEFAULT_FORCE_TIMEOUT = 2.0
STATE_FILE = "state.json"
LOG_FILE = "output.log"

# Run names may contain only letters, numbers, `_` and `-`.
RE_RUN_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
# Command, dependency and guard names share this alphabet.
RE_NAME = re.compile(r"[A-Za-z0-9_-]+")
# Named colors or six-digit hex colors.
RE_COLOR = re.compile(r"[A-Fa-f0-9]{6}|[A-Za-z]+")
# A run of duration components, such as `5`, `500ms` or `1m30s750ms`.
RE_DURATION = re.compile(r"(?:\d+(?:\.\d+)?(?:ms|m|s)?)+")

# Action names may not collide with guard names.
ACTIONS = frozenset({"silent", "noout", "noerr", "end"})

# Guard matching keeps only this many trailing characters of a stream.
GUARD_TAIL = 64_000

RE_DELAY = re.compile(
	r"^(?:(?P<minutes>\d+(?:\.\d+)?)m)?(?:(?P<seconds>\d+(?:\.\d+)?)s)?(?:(?P<milliseconds>\d+(?:\.\d+)?)ms)?$|^(?P<default>\d+(?:\.\d*)?)$"
)

# ANSI escape sequences, 7-bit and 8-bit C1.
# FROM: https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
RE_ANSI_ESCAPE_8BIT = re.compile(
	rb"(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])"
)
RE_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


# -----------------------------------------------------------------------------
#
# OPERATIONS
#
# -----------------------------------------------------------------------------

# NOTE: Process utilities


class Proc:
	"""Interrogates and controls operating-system processes."""

	available: ClassVar[bool] = Path("/proc").exists()

	@staticmethod
	def shell(command: list[str], stdin_data: bytes | None = None) -> bytes | None:
		"""Runs `command`, returning its stdout, or `None` when it fails."""
		result = subprocess.run(  # nosec: B603
			command, capture_output=True, input=stdin_data, check=False
		)
		return result.stdout if result.returncode == 0 else None

	@staticmethod
	def identity(pid: int) -> str | None:
		"""Returns an OS-provided identity that distinguishes reused PIDs."""
		if Proc.available:
			try:
				# Field 22 is the process start time. The comm field may contain
				# spaces, so strip the prefix through its closing parenthesis first.
				stat = Path(f"/proc/{pid}/stat").read_text()
				return stat[stat.rfind(")") + 2 :].split()[19]
			except (FileNotFoundError, IndexError, OSError):
				return None
		result = Proc.shell(["ps", "-o", "lstart=", "-p", str(pid)])
		return result.decode("utf8").strip() if result else None

	@staticmethod
	def children(pid: int) -> set[int]:
		"""Returns the descendant PIDs of `pid`."""
		if Proc.available:
			parents: dict[int, list[int]] = {}
			for proc_dir in Path("/proc").iterdir():
				if not (proc_dir.is_dir() and proc_dir.name.isdigit()):
					continue
				try:
					stat = (proc_dir / "stat").read_text().split()
					if len(stat) > 4:
						parents.setdefault(int(stat[3]), []).append(int(proc_dir.name))
				except (FileNotFoundError, IndexError, ValueError, OSError):
					continue
			res: set[int] = set()
			pending = [pid]
			while pending:
				for child in parents.get(pending.pop(), ()):
					if child not in res:
						res.add(child)
						pending.append(child)
			return res
		res = set()
		for line in (Proc.shell(["ps", "-g", str(pid)]) or b"").split(b"\n"):
			cpid = str(line.split()[0], "utf8") if line else None
			if cpid and cpid.isdigit():
				child_pid = int(cpid)
				if child_pid != pid:
					res.add(child_pid)
		return res

	@staticmethod
	def parent(pid: int) -> int | None:
		"""Returns the parent PID of `pid`, or None when unavailable."""
		if Proc.available:
			try:
				return int(Path(f"/proc/{pid}/stat").read_text().split()[3])
			except (FileNotFoundError, IndexError, ValueError, OSError):
				return None
		result = Proc.shell(["ps", "-o", "ppid=", "-p", str(pid)])
		if result:
			try:
				return int(result.decode("utf-8").strip())
			except ValueError:
				return None
		return None

	@staticmethod
	def exists(pid: int) -> bool:
		"""Returns True if `pid` refers to a live process."""
		if Proc.available:
			return Path(f"/proc/{pid}").exists()
		try:
			os.kill(pid, 0)
			return True
		except OSError:
			return False

	@staticmethod
	def kill(
		pid: int, sig: signal.Signals = signal.SIGTERM, use_group: bool = True
	) -> bool:
		"""Signals `pid`, and its whole process group when `use_group`."""
		try:
			if use_group:
				try:
					os.killpg(pid, sig)
				except OSError:
					pass
			try:
				os.kill(pid, sig)
			except ProcessLookupError as error:
				return error.errno == errno.ESRCH
			# Only attempted for real kills, as `waitpid` reaps the child.
			if sig in (signal.SIGTERM, signal.SIGKILL):
				try:
					os.waitpid(pid, os.WNOHANG)
				except OSError:
					pass
			return True
		except OSError:
			return False

	@staticmethod
	def mem(pid: int) -> tuple[str, str]:
		"""Returns the `(resident, peak)` memory usage of `pid`."""
		if Proc.available:
			try:
				mem = {
					k.strip(): v.strip()
					for k, v in (
						_.split(":", 1)
						for _ in Path(f"/proc/{pid}/status").read_text().split("\n")
						if ":" in _
					)
				}
				# SEE: <https://kernelnewbies.kernelnewbies.narkive.com/PG3s6Ndp/ot-meaning-of-proc-pid-status-fields>
				return mem["VmRSS"], mem["VmHWM"]
			except (FileNotFoundError, KeyError, IndexError):
				return "0 kB", "0 kB"
		result = Proc.shell(["ps", "-o", "rss,vsz", "-p", str(pid)])
		if result:
			try:
				lines = result.decode("utf-8").strip().split("\n")
				if len(lines) >= 2:
					values = lines[1].split()
					if len(values) >= 2:
						return values[0] + " kB", values[1] + " kB"
			except (ValueError, IndexError):
				pass
		return "0 kB", "0 kB"


# NOTE: Managed commands


class Command:
	"""A command started by a `Runner`, with its process and callbacks."""

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
		self.pgid: int | None = None
		self._children: set[int] = set()
		self.redirect_stop_event: threading.Event | None = None
		# Events (`start`, `out`, `err`, `end`) hidden from the formatter.
		self.suppressed: set[str] = set()
		self.on_start: list[StartCallback] = []
		self.on_out: list[OutCallback] = []
		self.on_err: list[ErrCallback] = []
		self.on_end: list[EndCallback] = []

	# TODO: We may want to have a recursive subprocess listing.
	@property
	def children(self) -> set[int]:
		"""Returns the known descendant PIDs of this command."""
		if self.pid:
			self._children = self._children.union(Proc.children(self.pid))
		return self._children

	@property
	def ppid(self) -> int | None:
		"""Returns the parent PID of this command's process."""
		return Proc.parent(self.pid) if self.pid else None

	@property
	def is_running(self) -> bool:
		"""Returns True while any process of this command is alive."""
		pids = set(self.children)
		if self.pid:
			pids.add(self.pid)
		return any(pid and Proc.exists(pid) for pid in pids)

	def silent(self) -> Command:
		"""Suppresses this command's start, output, error and end events."""
		self.suppressed.update({"start", "out", "err", "end"})
		return self


# NOTE: Formatting


def _write_stdout(data: bytes) -> None:
	"""Default `Formatter` sink, writing raw bytes to descriptor 1."""
	offset = 0
	while offset < len(data):
		offset += os.write(1, data[offset:])


def _now() -> datetime.datetime:
	"""Returns the current local time as a timezone-aware datetime."""
	return datetime.datetime.now(datetime.timezone.utc).astimezone()


class Formatter:
	"""Formats a stream of events coming from a `Runner`."""

	SEP = "│"
	STREAMS: ClassVar[dict[str, str]] = {
		"start": "$",
		"out": "<",
		"err": "!",
		"end": "=",
	}

	# ANSI color codes for named colors
	COLORS: ClassVar[dict[str, str]] = {
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
		writer: Callable[[bytes], None] | None = _write_stdout,
		timestamp: bool = False,
		relative: bool = False,
	) -> None:
		self.writer = writer
		self.timestamp = timestamp
		self.relative = relative
		self.start_time = _now() if timestamp else None

	def _get_timestamp_prefix(self) -> bytes:
		"""Generates the timestamp prefix of a log entry."""
		if not self.timestamp or not self.start_time:
			return b""
		current_time = _now()
		if self.relative:
			elapsed = current_time - self.start_time
			total_seconds = int(elapsed.total_seconds())
			hours = total_seconds // 3600
			minutes = (total_seconds % 3600) // 60
			seconds = total_seconds % 60
			timestamp_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
		else:
			timestamp_str = current_time.strftime("%H:%M:%S")
		return bytes(f"{timestamp_str}|", "utf8")

	def _get_color_code(self, color: str | None) -> str:
		"""Converts a named or hex `color` to an ANSI escape sequence."""
		if not color:
			return ""
		color_lower = color.lower()
		if color_lower in self.COLORS:
			return f"\033[{self.COLORS[color_lower]}m"
		if len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color):
			r = int(color[0:2], 16)
			g = int(color[2:4], 16)
			b = int(color[4:6], 16)
			return f"\033[38;2;{r};{g};{b}m"
		return ""

	def _apply_color(self, text: str, color: str | None) -> bytes:
		"""Wraps `text` in the ANSI sequence of `color`, returned as bytes."""
		if not color:
			return bytes(text, "utf8")
		color_code = self._get_color_code(color)
		if color_code:
			return bytes(f"{color_code}{text}\033[0m", "utf8")
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
		"""Writes `data` as `stream` events for command `key`."""
		if not self.writer:
			return
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
		# NOTE: Assemble each line before writing so concurrent commands never
		# interleave their timestamp, prefix and payload bytes.
		buffer = bytearray()
		for line in lines:
			buffer += timestamp_prefix
			buffer += stream_prefix
			buffer += colored_key
			buffer += sep_suffix
			buffer += line
			buffer += b"\n"
		self.writer(bytes(buffer))


def strip_ansi_bytes(data: bytes) -> bytes:
	"""Removes ANSI escape sequences from byte `data`."""
	return RE_ANSI_ESCAPE_8BIT.sub(b"", data)


def strip_ansi(data: str) -> str:
	"""Removes ANSI escape sequences from text `data`."""
	return RE_ANSI_ESCAPE.sub("", data)


# NOTE: Command-line grammar


def split_args(command: str) -> Iterable[str]:
	"""Splits shell-like `command` text while preserving quoted arguments."""
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


def _parse_sources(text: str, sigil: str) -> list[tuple[str, int]]:
	"""Parses `sigil`-prefixed stream sources from `text`."""
	if not text or not text.startswith(sigil):
		return []
	body = text[1:]
	if body.startswith("(") and body.endswith(")"):
		parts = [part.strip() for part in body[1:-1].split(",")]
	else:
		parts = [body]
	sources: list[tuple[str, int]] = []
	for part in parts:
		if not part:
			continue
		if part.startswith("1"):
			key, stream = part[1:], STDOUT
		elif part.startswith("2"):
			key, stream = part[1:], STDERR
		else:
			key, stream = part, STDOUT
		if key:
			sources.append((key, stream))
	return sources


# Function: parse_redirects
# Parses a `<SOURCE` stdin redirect specification.
def parse_redirects(redirects_str: str) -> Redirect | None:
	"""Parses redirects such as `<A`, `<2A`, `<(1A,2A)` or `<(A,B)`."""
	sources = _parse_sources(redirects_str, "<")
	if not sources:
		return None
	return Redirect([StreamSource(key, stream) for key, stream in sources])


# Function: parse_start_on_output
# Parses a `>SOURCE` start-on-output specification.
def parse_start_on_output(start_on_output_str: str) -> StartOnOutput | None:
	"""Parses conditions such as `>A`, `>2A`, `>(1A,2A)` or `>(A,B)`."""
	sources = _parse_sources(start_on_output_str, ">")
	if not sources:
		return None
	return StartOnOutput([StreamSource(key, stream) for key, stream in sources])


# Function: parse_delay
# Parses `delay_str` into seconds, or returns a non-numeric name unchanged.
def parse_delay(delay_str: str) -> float | str:
	"""Parses plain seconds, `ms`/`s`/`m` suffixes and combinations.

	Returns a duration in seconds, or the original token when it is not numeric.
	"""
	delay_str = delay_str.strip()
	match = RE_DELAY.match(delay_str)
	if match:
		default = match.group("default")
		if default:
			return float(default)
		total_seconds = 0.0
		if match.group("minutes"):
			total_seconds += float(match.group("minutes")) * 60.0
		if match.group("seconds"):
			total_seconds += float(match.group("seconds"))
		if match.group("milliseconds"):
			total_seconds += float(match.group("milliseconds")) / 1000.0
		return total_seconds
	try:
		return float(delay_str)
	except ValueError:
		return delay_str


# Function: _parse_streams
# Parses a `(1,2)` stream selector into a tuple of stream numbers.
def _parse_streams(text: str) -> tuple[int, ...]:
	streams: list[int] = []
	for part in text.split(","):
		if part.strip() == "1":
			streams.append(STDOUT)
		elif part.strip() == "2":
			streams.append(STDERR)
	return tuple(streams) if streams else (STDOUT,)


# Function: _scan_until
# Returns the index of the first character of `stop` at or after `start`.
def _scan_until(text: str, start: int, stop: str) -> int:
	for index in range(start, len(text)):
		if text[index] in stop:
			return index
	return len(text)


# Function: _scan_steps
# Scans a `+STEP`/`!GUARD` chain, returning the steps and the new cursor.
def _scan_steps(text: str, cursor: int) -> tuple[list[Delay], int]:
	steps: list[Delay] = []
	while cursor < len(text):
		if text[cursor] == "+":
			cursor += 1
			duration = RE_DURATION.match(text, cursor)
			if duration:
				parsed_delay = parse_delay(duration.group())
				if not isinstance(parsed_delay, float):
					break
				steps.append(parsed_delay)
				cursor = duration.end()
				continue
			name = RE_NAME.match(text, cursor)
			if not name:
				# A `+` may introduce the chain before a `!GUARD` step.
				if cursor < len(text) and text[cursor] in "!+":
					continue
				break
			key = name.group()
			cursor = name.end()
			start = False
			if cursor < len(text) and text[cursor] == "&":
				start = True
				cursor += 1
			streams: tuple[int, ...] = (STDOUT,)
			if cursor < len(text) and text[cursor] == "(":
				end = text.find(")", cursor)
				if end == -1:
					break
				streams = _parse_streams(text[cursor + 1 : end])
				cursor = end + 1
			if cursor < len(text) and text[cursor] == "|":
				guard = RE_NAME.match(text, cursor + 1)
				if guard and guard.group() not in ACTIONS:
					steps.append(ProcessGuard(key, streams, guard.group()))
					cursor = guard.end()
					continue
			steps.append(Wait(key, start))
		elif text[cursor] == "!":
			guard = RE_NAME.match(text, cursor + 1)
			if not guard:
				break
			steps.append(InputGuard(guard.group()))
			cursor = guard.end()
		else:
			break
	return steps, cursor


# Function: parse_dependencies
# Parses a `:KEY[&][+STEP...]` dependency specification.
def parse_dependencies(deps_str: str) -> list[Dependency]:
	"""Parses dependencies such as `:A`, `:A&`, `:A+1s` or `:A+!READY`."""
	if not deps_str or not deps_str.startswith(":"):
		return []
	dependencies: list[Dependency] = []
	cursor = 1
	while cursor < len(deps_str):
		if deps_str[cursor] == ":":
			cursor += 1
			continue
		name = RE_NAME.match(deps_str, cursor)
		if not name:
			break
		key = name.group()
		cursor = name.end()
		wait_for_start = False
		if cursor < len(deps_str) and deps_str[cursor] == "&":
			wait_for_start = True
			cursor += 1
		delays, cursor = _scan_steps(deps_str, cursor)
		dependencies.append(Dependency(key, wait_for_start, delays))
		if cursor < len(deps_str) and deps_str[cursor] == ":":
			cursor += 1
		else:
			break
	return dependencies


# Function: parse
# Parses a full command line into a `ParsedCommand`.
def parse(line: str) -> ParsedCommand:
	"""Parses `[KEY][#COLOR][+STEP...][<REDIR][>ONOUT][:DEP][|ACTION]=COMMAND`.

	Where `STEP` is a duration, `!GUARD` or `KEY[(STREAMS)]|GUARD`; `DEP` is
	`[KEY][&][+STEP...]`; `REDIR` is `<A`, `<2A`, `<(1A,2A)` or `<(A,B)`, and
	`ONOUT` is `>A`, `>2A`, `>(1A,2A)` or `>(A,B)`.
	"""
	cursor = 0
	name = RE_NAME.match(line, cursor)
	key = name.group() if name else None
	if name:
		cursor = name.end()
	color = None
	if cursor < len(line) and line[cursor] == "#":
		color_match = RE_COLOR.match(line, cursor + 1)
		if color_match:
			color = color_match.group()
			cursor = color_match.end()
	steps, cursor = _scan_steps(line, cursor)
	redirects_str = ""
	if cursor < len(line) and line[cursor] == "<":
		end = _scan_until(line, cursor + 1, ":|>=")
		redirects_str = line[cursor:end]
		cursor = end
	start_on_output_str = ""
	if cursor < len(line) and line[cursor] == ">":
		end = _scan_until(line, cursor + 1, ":|=")
		start_on_output_str = line[cursor:end]
		cursor = end
	deps_str = ""
	if cursor < len(line) and line[cursor] == ":":
		end = _scan_until(line, cursor + 1, "|=")
		deps_str = line[cursor:end]
		cursor = end
	actions: list[str] = []
	while cursor < len(line) and line[cursor] == "|":
		action = re.match(r"\|[a-z]+", line[cursor:])
		if not action:
			break
		actions.append(action.group()[1:])
		cursor += action.end()

	if cursor >= len(line) or line[cursor] != "=":
		# No valid prefix: the whole line is the command.
		return ParsedCommand(
			key=None,
			color=None,
			start_delay=0.0,
			dependencies=[],
			redirects=None,
			start_on_output=None,
			actions=[],
			command=list(split_args(line)),
		)

	if steps and all(isinstance(step, float) for step in steps):
		start_delay = sum(step for step in steps if isinstance(step, float))
		start_steps: list[Delay] = []
	else:
		start_delay = 0.0
		start_steps = steps

	return ParsedCommand(
		key=key,
		color=color,
		start_delay=start_delay,
		dependencies=parse_dependencies(deps_str),
		redirects=parse_redirects(redirects_str),
		start_on_output=parse_start_on_output(start_on_output_str),
		actions=actions,
		command=list(split_args(line[cursor + 1 :])),
		start_steps=start_steps,
	)


# NOTE: Guards


# Function: _glob_to_regex
# Translates a `*`/`?` glob into an unanchored regular expression.
def _glob_to_regex(pattern: str) -> str:
	return "".join(
		".*" if char == "*" else "." if char == "?" else re.escape(char)
		for char in pattern
	)


class Guard:
	"""A named, latched condition matched against a stream of text."""

	def __init__(self, name: str, pattern: str, regex: bool = False) -> None:
		self.name = name
		self.pattern = pattern
		self.regex = regex
		self.event = threading.Event()
		self.matcher = (
			re.compile(pattern) if regex else re.compile(_glob_to_regex(pattern))
		)

	def matches(self, text: str) -> bool:
		"""Returns True when `text` satisfies the guard pattern."""
		return self.matcher.search(text) is not None


# Function: parse_guard_definition
# Parses `@NAME=EXPR` or `@NAME:re=EXPR`, or returns None when not a definition.
def parse_guard_definition(argument: str) -> tuple[str, str, bool] | None:
	"""Parses a guard definition; `EXPR` is a glob unless `:re` is used."""
	if not argument.startswith("@"):
		return None
	head, separator, expression = argument[1:].partition("=")
	if not separator:
		return None
	regex = head.endswith(":re")
	if regex:
		head = head[:-3]
	if not RE_RUN_NAME.fullmatch(head):
		raise SyntaxError(f"Invalid guard name: {head!r}")
	return head, expression, regex


# NOTE: Runner


class Runner:
	"""Orchestrates commands: starts, joins, terminates and dispatches events.

	`Runner.Get()` exposes the shared default instance used by the module-level
	`run`, `join` and `terminate` functions. Callers that need their own
	configuration or lifecycle (the CLI and the detached supervisor) construct
	a `Runner` directly instead.
	"""

	SIGNALS: ClassVar[dict[str, int]] = {
		name: getattr(signal, name).value
		for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGCHLD")
		if hasattr(signal, name)
	}
	INSTANCE: ClassVar[Runner | None] = None

	@classmethod
	def Get(cls) -> Runner:
		"""Returns the process-wide default runner."""
		if cls.INSTANCE is None:
			cls.INSTANCE = Runner(register_signals=True)
		return cls.INSTANCE

	def __init__(
		self,
		timestamp: bool = False,
		relative: bool = False,
		register_signals: bool = False,
	) -> None:
		self.commands: dict[str, tuple[Command, threading.Thread]] = {}
		self.process_started: dict[str, threading.Event] = {}
		self.process_outputs: dict[str, dict[int, list[bytes]]] = {}
		self.output_events: dict[str, dict[int, threading.Event]] = {}
		self.formatter: Formatter = Formatter(timestamp=timestamp, relative=relative)
		self.graceful_timeout: float = DEFAULT_GRACEFUL_TIMEOUT
		self.force_timeout: float = DEFAULT_FORCE_TIMEOUT
		self.guards: dict[str, Guard] = {}
		self._guard_watchers: dict[tuple[str, int], list[Guard]] = {}
		self._guard_tails: dict[tuple[str, int], str] = {}
		self._stdin_guards: list[Guard] = []
		self._stdin_tail: str = ""
		self._stdin_thread: threading.Thread | None = None
		if register_signals:
			self.register_signals()

	# NOTE: Guards

	def define_guard(self, name: str, pattern: str, regex: bool = False) -> Guard:
		"""Defines (or replaces) the guard `name` matching `pattern`."""
		guard = Guard(name, pattern, regex)
		self.guards[name] = guard
		return guard

	def _guard(self, name: str) -> Guard:
		guard = self.guards.get(name)
		if guard is None:
			raise ValueError(f"Undefined guard: {name}")
		return guard

	def _watch_guard_process(self, key: str, stream: int, guard: Guard) -> None:
		"""Maps `guard` to a running command's `stream` and its buffered tail."""
		watchers = self._guard_watchers.setdefault((key, stream), [])
		if guard not in watchers:
			watchers.append(guard)
		if guard.matches(self._guard_tails.get((key, stream), "")):
			guard.event.set()

	def _watch_guard_stdin(self, guard: Guard) -> None:
		"""Maps `guard` to multiplex's standard input."""
		if guard not in self._stdin_guards:
			self._stdin_guards.append(guard)
		if self._stdin_thread is None:
			self._stdin_thread = threading.Thread(
				target=self._read_stdin, daemon=True
			)
			self._stdin_thread.start()

	def _read_stdin(self) -> None:
		"""Feeds multiplex's standard input to the registered input guards."""
		while True:
			try:
				chunk = os.read(0, 64_000)
			except OSError:
				return
			if not chunk:
				return
			self._stdin_tail = (
				self._stdin_tail + chunk.decode("utf8", "replace")
			)[-GUARD_TAIL:]
			for guard in self._stdin_guards:
				if guard.matches(self._stdin_tail):
					guard.event.set()

	def _apply_step(self, step: Delay) -> None:
		"""Applies a single delay-chain step."""
		if isinstance(step, float):
			time.sleep(step)
		elif isinstance(step, Wait):
			if step.start:
				self._wait_for_process_start(step.key)
			else:
				self._wait_for_process(step.key)
		elif isinstance(step, InputGuard):
			guard = self._guard(step.name)
			self._watch_guard_stdin(guard)
			guard.event.wait()
		elif isinstance(step, ProcessGuard):
			guard = self._guard(step.name)
			for stream in step.streams:
				self._watch_guard_process(step.key, stream, guard)
			guard.event.wait()

	def active_commands(
		self, commands: dict[str, tuple[Command, threading.Thread]] | None = None
	) -> dict[str, tuple[Command, threading.Thread]]:
		"""Returns the subset of `commands` whose reader thread is alive."""
		commands = commands or self.commands
		return {k: v for k, v in commands.items() if v[1].is_alive()}

	# NOTE: Event dispatching

	def do_start(self, command: Command) -> None:
		if command.on_start:
			for callback in command.on_start:
				callback(command)
		elif "start" not in command.suppressed:
			self.formatter.start(command)

	def do_out(self, command: Command, data: bytes) -> None:
		if command.on_out:
			for callback in command.on_out:
				callback(command, data)
		elif "out" not in command.suppressed:
			self.formatter.out(command, data)

	def do_err(self, command: Command, data: bytes) -> None:
		if command.on_err:
			for callback in command.on_err:
				callback(command, data)
		elif "err" not in command.suppressed:
			self.formatter.err(command, data)

	def do_end(self, command: Command, data: int) -> None:
		if command.redirect_stop_event:
			command.redirect_stop_event.set()
		if command.on_end:
			for callback in command.on_end:
				callback(command, data)
		elif "end" not in command.suppressed:
			self.formatter.end(command, data)

	# NOTE: Waiting

	def _wait_for_process(self, proc: str) -> None:
		"""Waits for the named command to complete."""
		if proc in self.commands:
			_, thread = self.commands[proc]
			thread.join()

	def _wait_for_process_start(self, proc: str) -> None:
		"""Waits for the named command to start."""
		event = self.process_started.get(proc)
		if event:
			event.wait()

	def _wait_for_output(self, proc: str, stream: int) -> None:
		"""Waits for the named command to produce output on `stream`."""
		events = self.output_events.get(proc)
		if events and stream in events:
			events[stream].wait()

	# NOTE: Running

	def run(
		self,
		command: list[str],
		key: str | None = None,
		color: str | None = None,
		start_delay: float = 0.0,
		dependencies: list[Dependency] | None = None,
		redirects: Redirect | None = None,
		start_on_output: StartOnOutput | None = None,
		actions: list[str] | None = None,
		start_steps: list[Delay] | None = None,
		on_start: StartCallback | None = None,
		on_out: OutCallback | None = None,
		on_err: ErrCallback | None = None,
		on_end: EndCallback | None = None,
	) -> Command:
		"""Starts `command` and returns its `Command` handle."""
		key = key or str(len(self.commands))
		cmd = Command(command, key, color)
		if on_start:
			cmd.on_start.append(on_start)
		if on_out:
			cmd.on_out.append(on_out)
		if on_err:
			cmd.on_err.append(on_err)
		if on_end:
			cmd.on_end.append(on_end)
		if actions:
			if "silent" in actions:
				cmd.silent()
			if "noout" in actions:
				cmd.suppressed.add("out")
			if "noerr" in actions:
				cmd.suppressed.add("err")

		self.process_started[key] = threading.Event()
		self.process_outputs[key] = {STDOUT: [], STDERR: []}
		self.output_events[key] = {
			STDOUT: threading.Event(),
			STDERR: threading.Event(),
		}

		stdin_pipe: int | None = None
		if redirects:
			stdin_read_fd, stdin_write_fd = os.pipe()
			stdin_pipe = stdin_read_fd
			redirect_stop_event = threading.Event()
			process_outputs = self.process_outputs

			def redirect_manager() -> None:
				try:
					while not redirect_stop_event.is_set():
						for source in redirects.sources:
							buffer = process_outputs.get(source.key, {}).get(
								source.stream
							)
							if not buffer:
								continue
							data = b"".join(buffer)
							buffer.clear()
							if data:
								try:
									os.write(stdin_write_fd, data)
								except (OSError, BrokenPipeError):
									return
						time.sleep(0.001)
				except (OSError, BrokenPipeError):
					pass
				finally:
					try:
						os.close(stdin_write_fd)
					except OSError:
						pass

			threading.Thread(target=redirect_manager, daemon=True).start()
			cmd.redirect_stop_event = redirect_stop_event

		if start_on_output:
			for source in start_on_output.sources:
				if source.key not in self.output_events:
					self.output_events[source.key] = {
						STDOUT: threading.Event(),
						STDERR: threading.Event(),
					}
				self._wait_for_output(source.key, source.stream)

		if dependencies:
			for dep in dependencies:
				if dep.wait_for_start:
					self._wait_for_process_start(dep.key)
				else:
					self._wait_for_process(dep.key)
				for step in dep.delays:
					self._apply_step(step)

		if start_steps:
			for step in start_steps:
				self._apply_step(step)
		elif start_delay > 0:
			time.sleep(start_delay)

		# NOTE: With start_new_session set, children join the process group whose
		# id is the command's pid.
		process = subprocess.Popen(	 # nosec: B603
			command,
			stdin=stdin_pipe,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			bufsize=0,
			start_new_session=True,
		)
		cmd.pid = process.pid
		cmd.pgid = process.pid
		self.process_started[key].set()

		def on_process_end(exit_code: int) -> None:
			self.do_end(cmd, exit_code)
			if "end" in (actions or ()):
				# NOTE: Called from the reader thread, so potentially problematic.
				self.terminate()

		# NOTE: A single selecting reader thread per process keeps buffering low.
		thread = threading.Thread(
			target=self.reader_threaded,
			args=(
				process,
				lambda data: self.do_out(cmd, data),
				lambda data: self.do_err(cmd, data),
				on_process_end,
				key,
			),
		)
		self.commands[key] = (cmd, thread)
		thread.start()
		self.do_start(cmd)
		return cmd

	def reader_threaded(
		self,
		process: subprocess.Popen[bytes],
		out: BytesConsumer | None = None,
		err: BytesConsumer | None = None,
		end: Callable[[int], None] | None = None,
		capture_key: str | None = None,
	) -> None:
		"""Streams a process' channels to `out` and `err` until they close."""
		channels: dict[int, tuple[int, BytesConsumer | None]] = {}
		if process.stdout is not None:
			channels[process.stdout.fileno()] = (STDOUT, out)
		if process.stderr is not None:
			channels[process.stderr.fileno()] = (STDERR, err)
		while waiting := list(channels):
			for fd in select.select(waiting, [], [])[0]:
				chunk = os.read(fd, 64_000)
				if chunk:
					stream, handler = channels[fd]
					self._capture_output(capture_key, stream, chunk)
					if handler:
						handler(chunk)
				else:
					# NOTE: We must not close the descriptor, we did not open it.
					del channels[fd]
		if end:
			end(process.returncode or 0)

	def _capture_output(self, key: str | None, stream: int, chunk: bytes) -> None:
		"""Buffers `chunk`, signals first output and feeds process guards."""
		if not key:
			return
		tail = (
			self._guard_tails.get((key, stream), "")
			+ chunk.decode("utf8", "replace")
		)[-GUARD_TAIL:]
		self._guard_tails[(key, stream)] = tail
		for guard in self._guard_watchers.get((key, stream), ()):
			if guard.matches(tail):
				guard.event.set()
		if key not in self.process_outputs:
			return
		self.process_outputs[key][stream].append(chunk)
		events = self.output_events.get(key)
		if events and not events[stream].is_set():
			events[stream].set()

	# NOTE: Joining and terminating

	def join(self, *commands: Command, timeout: int | None = None) -> list[Command]:
		"""Waits for `commands` (or all), up to `timeout`, returning survivors."""
		selection = (
			{k: v for k, v in self.commands.items() if v[0] in commands}
			if commands
			else self.commands
		)
		started = time.time()
		elapsed: float = 0.0
		poll_timeout = 1.0
		while (active := self.active_commands(selection)) and (
			timeout is None or elapsed < timeout
		):
			t = min(poll_timeout, timeout / len(active)) if timeout else poll_timeout
			for cmd, thread in active.values():
				# NOTE: Waiting on the child avoids leaving it in a zombie state.
				# SEE: <https://en.wikipedia.org/wiki/Zombie_process>
				if cmd.pid:
					try:
						os.waitpid(cmd.pid, os.WNOHANG)
					except OSError:
						pass
				thread.join(timeout=t)
			elapsed = time.time() - started
		return [command for command, _ in self.active_commands(selection).values()]

	def _signal_command(
		self, command: Command, sig: signal.Signals, killed: set[int]
	) -> None:
		"""Signals `command`'s process group once per pid in `killed`."""
		pids = set(command.children)
		if command.pid:
			pids.add(command.pid)
		for pid in pids:
			if pid is None or pid in killed:
				continue
			if Proc.exists(pid) and Proc.kill(pid, sig, use_group=True):
				killed.add(pid)

	def terminate(
		self, *commands: Command, graceful: bool = True, timeout: int | None = None
	) -> bool:
		"""Terminates `commands` (or all), gracefully then forcefully.

		`timeout` overrides `graceful_timeout` for the SIGTERM phase. Returns
		True when every command is gone, False if `force_timeout` elapsed first.
		"""
		grace_timeout = timeout or self.graceful_timeout
		selection = (
			{k: v for k, v in self.commands.items() if v[0] in commands}
			if commands
			else self.commands
		)
		if not selection:
			return True

		if graceful:
			started = time.time()
			killed: set[int] = set()
			for cmd, _ in selection.values():
				self._signal_command(cmd, signal.SIGTERM, killed)
			while selection and (time.time() - started) < grace_timeout:
				selection = self.active_commands(selection)
				if selection:
					time.sleep(0.1)
			if not selection:
				return True

		started = time.time()
		killed = set()
		while selection:
			for cmd, _ in selection.values():
				self._signal_command(cmd, signal.SIGKILL, killed)
			if (time.time() - started) >= self.force_timeout:
				return False
			selection = self.active_commands(selection)
			if selection:
				time.sleep(0.1)
		return True

	# NOTE: Signals

	def register_signals(self) -> None:
		"""Installs graceful handlers for `SIGINT`, `SIGTERM` and `SIGHUP`."""
		for signame in ("SIGINT", "SIGTERM", "SIGHUP"):
			if hasattr(signal, signame):
				try:
					signal.signal(getattr(signal, signame), self.on_signal)
				except (OSError, ValueError):
					# Signal not available on this platform.
					pass

	def propagate_signal(self, signum: int) -> None:
		"""Propagates `signum` to every active child process."""
		for cmd, _ in self.active_commands(None).values():
			if not cmd.pid:
				continue
			pids = set(cmd.children)
			pids.add(cmd.pid)
			for pid in pids:
				if pid and Proc.exists(pid):
					try:
						Proc.kill(pid, signal.Signals(signum), use_group=True)
					except (OSError, ValueError):
						# Process might have died or the signal is invalid.
						pass

	def on_signal(self, signum: int, frame: object) -> None:
		"""Handles a termination signal by shutting every command down."""
		signame = next((k for k, v in self.SIGNALS.items() if v == signum), None)
		if signame in ("SIGINT", "SIGTERM", "SIGHUP"):
			print(f"\nReceived {signame}, gracefully shutting down processes...")
			self.propagate_signal(signum)
			if not self.terminate(graceful=True):
				print("Graceful shutdown failed, forcing termination...")
				self.terminate(graceful=False)
			remaining = self.join(timeout=int(self.force_timeout))
			if remaining:
				print(f"Warning: {len(remaining)} processes did not terminate cleanly")
			sys.exit(0)
		elif signame == "SIGCHLD":
			pass


# NOTE: Detached run state


class Run:
	"""Manages the filesystem-backed state of a detached run."""

	@staticmethod
	def Directory(state_dir: str, name: str) -> Path:
		"""Returns the directory of run `name`, validating `name`."""
		if not RE_RUN_NAME.fullmatch(name):
			raise ValueError("Run names may contain only letters, numbers, '_' and '-'")
		return Path(state_dir).resolve() / name

	@staticmethod
	def StatePath(state_dir: str, name: str) -> Path:
		"""Returns the `state.json` path of run `name`."""
		return Run.Directory(state_dir, name) / STATE_FILE

	@staticmethod
	def LogPath(state_dir: str, name: str) -> Path:
		"""Returns the `output.log` path of run `name`."""
		return Run.Directory(state_dir, name) / LOG_FILE

	@staticmethod
	def IsActive(state: dict[str, object] | None) -> bool:
		"""Returns True when `state` describes a live supervisor process."""
		if not state or state.get("status") != STATUS_RUNNING:
			return False
		pid = state.get("supervisor_pid")
		identity = state.get("supervisor_identity")
		if not isinstance(pid, int) or not isinstance(identity, str):
			return False
		return Proc.exists(pid) and Proc.identity(pid) == identity

	@staticmethod
	def Read(path: Path) -> dict[str, object] | None:
		"""Reads a JSON object from `path`, or None when unavailable."""
		try:
			value = json.loads(path.read_text(encoding="utf8"))
			return value if isinstance(value, dict) else None
		except (FileNotFoundError, json.JSONDecodeError, OSError):
			return None

	@staticmethod
	def Write(path: Path, value: dict[str, object]) -> None:
		"""Atomically writes `value` so readers never observe partial JSON."""
		path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
		temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
		with temporary.open("w", encoding="utf8") as output:
			json.dump(value, output, sort_keys=True)
			output.write("\n")
			output.flush()
			os.fsync(output.fileno())
		os.replace(temporary, path)

	@staticmethod
	def Update(path: Path, **changes: object) -> dict[str, object]:
		"""Merges `changes` into the state at `path`, returning the new value."""
		state = Run.Read(path) or {}
		state.update(changes)
		Run.Write(path, state)
		return state

	@staticmethod
	def Stop(state_dir: str, name: str, wait: bool = False) -> bool:
		"""Signals run `name`'s supervisor, optionally waiting for it to exit."""
		state_file = Run.StatePath(state_dir, name)
		state = Run.Read(state_file)
		if not Run.IsActive(state):
			return False
		assert state is not None
		pid = state["supervisor_pid"]
		assert isinstance(pid, int)
		os.kill(pid, signal.SIGTERM)
		if wait:
			deadline = time.monotonic() + 8.0
			while time.monotonic() < deadline and Run.IsActive(Run.Read(state_file)):
				time.sleep(0.05)
		return True

	@staticmethod
	def Supervise(
		name: str,
		state_dir: str,
		commands: list[str],
		timestamp: bool,
		relative: bool,
		prune_after: float,
		run_id: str,
		guards: list[str] | None = None,
	) -> None:
		"""Runs a detached multiplex session and persists its observable state."""
		run_dir = Run.Directory(state_dir, name)
		state_file = run_dir / STATE_FILE
		log_file = run_dir / LOG_FILE
		pid = os.getpid()
		identity = Proc.identity(pid)
		if identity is None:
			raise RuntimeError("Could not determine supervisor process identity")

		with log_file.open("ab", buffering=0) as log:
			def write_log(data: bytes) -> None:
				log.write(data)

			runner = Runner(
				timestamp=timestamp,
				relative=relative,
				register_signals=True,
			)
			runner.formatter.writer = write_log
			for definition in guards or ():
				parsed_guard = parse_guard_definition(definition)
				assert parsed_guard is not None
				guard_name, expression, regex = parsed_guard
				runner.define_guard(guard_name, expression, regex)
			Run.Update(
				state_file,
				name=name,
				run_id=run_id,
				status=STATUS_RUNNING,
				supervisor_pid=pid,
				supervisor_identity=identity,
				started_at=time.time(),
				commands=[],
				command_lines=commands,
			)
			completed = False
			failure: str | None = None
			command_entries: list[dict[str, object]] = []
			try:
				for line in commands:
					parsed = parse(line)
					command = runner.run(
						parsed.command,
						key=parsed.key,
						color=parsed.color,
						start_delay=parsed.start_delay,
						dependencies=parsed.dependencies,
						redirects=parsed.redirects,
						start_on_output=parsed.start_on_output,
						actions=parsed.actions,
						start_steps=parsed.start_steps,
					)
					command_entries.append(
						{"key": command.key, "pid": command.pid, "pgid": command.pgid}
					)
					Run.Update(state_file, commands=command_entries)
				runner.join()
				completed = True
			except SystemExit:
				# Runner's signal handler exits the supervisor after terminating
				# its children; keep running long enough to prune the state.
				completed = True
			except Exception as error:	# noqa: BLE001 - record any supervisor failure
				failure = str(error)
				log.write(f"multiplex supervisor failed: {failure}\n".encode())
			finally:
				Run.Update(
					state_file,
					status=STATUS_STOPPED if completed else STATUS_FAILED,
					stopped_at=time.time(),
					error=failure,
				)

		# Keep the completed log briefly for inspection, then leave no stale state.
		if prune_after > 0:
			time.sleep(prune_after)
		# --replace may have installed a new state directory while this supervisor
		# was waiting. Never prune a run that does not belong to this supervisor.
		if (Run.Read(state_file) or {}).get("run_id") == run_id:
			shutil.rmtree(run_dir, ignore_errors=True)


# NOTE: Command-line interface


class CLI:
	"""Command-line interface, one static method per subcommand."""

	@staticmethod
	def AddStateDir(parser: argparse.ArgumentParser) -> None:
		"""Adds the shared `--state-dir` option to `parser`."""
		parser.add_argument("--state-dir", default=DEFAULT_STATE_DIR)

	@staticmethod
	def AddTimeOptions(parser: argparse.ArgumentParser) -> None:
		"""Adds the shared timestamp options to `parser`."""
		parser.add_argument("--time", action="store_true")
		parser.add_argument("--time-relative", action="store_true")

	@staticmethod
	def ExtractTimeMode(argv: list[str]) -> tuple[list[str], str | None]:
		"""Extracts `--time[=MODE]`, returning the remaining arguments."""
		time_mode: str | None = None
		filtered: list[str] = []
		for arg in argv:
			if arg == "--time":
				time_mode = "absolute"
			elif arg.startswith("--time="):
				value = arg.split("=", 1)[1]
				if value not in ("absolute", "relative"):
					raise ValueError(f"Invalid time mode: {value}")
				time_mode = value
			else:
				filtered.append(arg)
		return filtered, time_mode

	@staticmethod
	def SplitGuards(arguments: list[str]) -> tuple[list[str], list[str]]:
		"""Splits command arguments from `@NAME=EXPR` guard definitions."""
		commands: list[str] = []
		definitions: list[str] = []
		for argument in arguments:
			if argument.startswith("@"):
				definitions.append(argument)
			else:
				commands.append(argument)
		return commands, definitions

	@staticmethod
	def ParseGuards(definitions: list[str]) -> list[tuple[str, str, bool]]:
		"""Parses `@NAME=EXPR` definitions, raising on invalid ones."""
		parsed: list[tuple[str, str, bool]] = []
		for definition in definitions:
			value = parse_guard_definition(definition)
			if value is None:
				raise ValueError(f"Invalid guard definition: {definition}")
			parsed.append(value)
		return parsed

	@staticmethod
	def Start(argv: list[str]) -> None:
		"""Starts a detached run."""
		parser = argparse.ArgumentParser(prog="multiplex start")
		CLI.AddStateDir(parser)
		parser.add_argument("--replace", action="store_true")
		parser.add_argument("--prune-after", type=float, default=DEFAULT_PRUNE_AFTER)
		CLI.AddTimeOptions(parser)
		parser.add_argument("name")
		parser.add_argument("commands", nargs="+")
		args = parser.parse_args(argv)
		if args.prune_after < 0:
			parser.error("--prune-after must not be negative")
		commands, definitions = CLI.SplitGuards(args.commands)
		if not commands:
			parser.error("at least one command is required")
		try:
			CLI.ParseGuards(definitions)
		except (SyntaxError, ValueError) as error:
			parser.error(str(error))
		try:
			run_dir = Run.Directory(args.state_dir, args.name)
		except ValueError as error:
			parser.error(str(error))
		state_file = run_dir / STATE_FILE
		previous = Run.Read(state_file)
		if Run.IsActive(previous):
			if not args.replace:
				parser.error(
					f"run '{args.name}' is already active (use --replace to replace it)"
				)
			Run.Stop(args.state_dir, args.name, wait=True)
		if run_dir.exists():
			shutil.rmtree(run_dir, ignore_errors=True)
		run_dir.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
		try:
			run_dir.mkdir(mode=0o700)
		except FileExistsError:
			parser.error(f"run '{args.name}' is already being started")
		run_id = uuid.uuid4().hex
		Run.Write(
			state_file,
			{"name": args.name, "run_id": run_id, "status": STATUS_STARTING},
		)

		child_args = [
			sys.executable,
			str(Path(__file__).resolve()),
			"_supervise",
			"--state-dir",
			str(Path(args.state_dir).resolve()),
			"--prune-after",
			str(args.prune_after),
			"--run-id",
			run_id,
		]
		if args.time:
			child_args.append("--time")
		if args.time_relative:
			child_args.append("--time-relative")
		for definition in definitions:
			child_args.extend(["--guard", definition])
		child_args.extend([args.name, *commands])
		with open(os.devnull, "wb") as devnull:
			subprocess.Popen(  # nosec: B603
				child_args,
				stdin=devnull,
				stdout=devnull,
				stderr=devnull,
				start_new_session=True,
			)
		deadline = time.monotonic() + 5.0
		while time.monotonic() < deadline:
			state = Run.Read(state_file)
			if Run.IsActive(state):
				return
			if state and state.get("status") == STATUS_STOPPED:
				return
			if state and state.get("status") == STATUS_FAILED:
				parser.error(
					f"run '{args.name}' failed: {state.get('error', 'unknown error')}"
				)
			time.sleep(0.02)
		parser.error(
			f"run '{args.name}' failed to start; inspect {run_dir / LOG_FILE}"
		)

	@staticmethod
	def Stop(argv: list[str]) -> None:
		"""Stops a detached run."""
		parser = argparse.ArgumentParser(prog="multiplex stop")
		CLI.AddStateDir(parser)
		parser.add_argument("name")
		args = parser.parse_args(argv)
		try:
			stopped = Run.Stop(args.state_dir, args.name, wait=True)
		except ValueError as error:
			parser.error(str(error))
		if not stopped:
			parser.error(f"no active run named '{args.name}'")

	@staticmethod
	def Status(argv: list[str]) -> None:
		"""Lists detached runs and their status."""
		parser = argparse.ArgumentParser(prog="multiplex status")
		CLI.AddStateDir(parser)
		parser.add_argument("name", nargs="?")
		args = parser.parse_args(argv)
		root = Path(args.state_dir)
		if args.name:
			names = [args.name]
		elif root.exists():
			names = [path.name for path in root.iterdir() if path.is_dir()]
		else:
			names = []
		for name in sorted(names):
			try:
				state = Run.Read(Run.StatePath(args.state_dir, name))
			except ValueError as error:
				parser.error(str(error))
			if Run.IsActive(state):
				assert state is not None
				print(f"{name}\trunning\tpid {state['supervisor_pid']}")
			elif state:
				print(f"{name}\tstopped")

	@staticmethod
	def Tail(argv: list[str]) -> None:
		"""Prints (and optionally follows) a run's log."""
		parser = argparse.ArgumentParser(prog="multiplex tail")
		CLI.AddStateDir(parser)
		parser.add_argument("-f", "--follow", action="store_true")
		parser.add_argument("name")
		args = parser.parse_args(argv)
		try:
			log_file = Run.LogPath(args.state_dir, args.name)
		except ValueError as error:
			parser.error(str(error))
		if not log_file.exists():
			parser.error(f"no log for run '{args.name}'")
		with log_file.open("rb") as log:
			while True:
				data = log.read()
				if data:
					os.write(1, data)
				elif not args.follow or not log_file.exists():
					return
				else:
					time.sleep(0.1)

	@staticmethod
	def Supervise(argv: list[str]) -> None:
		"""Runs the detached supervisor process (internal)."""
		parser = argparse.ArgumentParser(prog="multiplex _supervise")
		parser.add_argument("--state-dir", required=True)
		parser.add_argument("--prune-after", type=float, required=True)
		parser.add_argument("--run-id", required=True)
		parser.add_argument("--guard", action="append", default=[])
		CLI.AddTimeOptions(parser)
		parser.add_argument("name")
		parser.add_argument("commands", nargs="+")
		args = parser.parse_args(argv)
		Run.Supervise(
			args.name,
			args.state_dir,
			args.commands,
			args.time or args.time_relative,
			args.time_relative,
			args.prune_after,
			args.run_id,
			args.guard,
		)

	@staticmethod
	def Main(argv: list[str] | str = sys.argv[1:]) -> None:
		"""The command-line entry point of this module."""
		if isinstance(argv, str):
			argv = [argv]
		elif not isinstance(argv, (list, tuple)):
			argv = [str(argv)]
		commands = {
			"start": CLI.Start,
			"stop": CLI.Stop,
			"status": CLI.Status,
			"tail": CLI.Tail,
			"_supervise": CLI.Supervise,
		}
		if argv and (handler := commands.get(argv[0])):
			handler(list(argv[1:]))
			return

		# TODO: Rework the command line arguments to follow common usage patterns.
		oparser = argparse.ArgumentParser(prog="multiplex")
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
		time_group = oparser.add_mutually_exclusive_group()
		time_group.add_argument(
			"--time",
			action="store_const",
			const="absolute",
			dest="time_mode",
			default=None,
			help="Adds absolute timestamps (HH:MM:SS); `--time=relative` for relative",
		)
		time_group.add_argument(
			"--time-relative",
			action="store_const",
			const="relative",
			dest="time_mode",
			default=None,
			help="Adds relative timestamps (00:00:00 start)",
		)
		try:
			filtered_argv, time_mode = CLI.ExtractTimeMode(argv)
		except ValueError as error:
			oparser.error(str(error))
		args = oparser.parse_args(args=filtered_argv)
		if time_mode is not None:
			args.time_mode = time_mode

		out_path = args.output if args.output and args.output != "-" else None
		try:
			if out_path:
				with open(out_path, "wt") as out:
					CLI.Execute(args, out)
			else:
				CLI.Execute(args, sys.stdout)
		except (SyntaxError, ValueError) as error:
			oparser.error(str(error))

	@staticmethod
	def Execute(args: argparse.Namespace, out: TextIO) -> None:
		"""Parses or runs `args.commands`, writing parse output to `out`."""
		commands, definitions = CLI.SplitGuards(args.commands)
		if args.parse:
			for command in commands:
				parsed_cmd = parse(command)
				out.write(f"Parsed: {command}\n")
				out.write(f"- key: {parsed_cmd.key}\n")
				out.write(f"- color: {parsed_cmd.color}\n")
				out.write(f"- start_delay: {parsed_cmd.start_delay}\n")
				out.write(f"- start_steps: {parsed_cmd.start_steps}\n")
				out.write(f"- dependencies: {parsed_cmd.dependencies}\n")
				out.write(f"- redirects: {parsed_cmd.redirects}\n")
				out.write(f"- start_on_output: {parsed_cmd.start_on_output}\n")
				out.write(f"- actions: {parsed_cmd.actions}\n")
				out.write(f"- cmd: {parsed_cmd.command}\n")
			return
		runner = Runner(
			timestamp=args.time_mode is not None,
			relative=args.time_mode == "relative",
			register_signals=True,
		)
		for guard_name, expression, regex in CLI.ParseGuards(definitions):
			runner.define_guard(guard_name, expression, regex)
		for command in commands:
			parsed_cmd = parse(command)
			runner.run(
				parsed_cmd.command,
				key=parsed_cmd.key,
				color=parsed_cmd.color,
				start_delay=parsed_cmd.start_delay,
				dependencies=parsed_cmd.dependencies,
				redirects=parsed_cmd.redirects,
				start_on_output=parsed_cmd.start_on_output,
				actions=parsed_cmd.actions,
				start_steps=parsed_cmd.start_steps,
			)
		if args.timeout:
			runner.join(timeout=args.timeout)
			runner.terminate()
			runner.join()
		else:
			runner.join()


# -----------------------------------------------------------------------------
#
# API
#
# -----------------------------------------------------------------------------


def run(
	*args: str | int,
	on_start: StartCallback | None = None,
	on_out: OutCallback | None = None,
	on_err: ErrCallback | None = None,
	on_end: EndCallback | None = None,
) -> Command:
	"""Starts a command on the default runner with optional event callbacks."""
	return Runner.Get().run(
		[str(_) for _ in args],
		on_start=on_start,
		on_out=on_out,
		on_err=on_err,
		on_end=on_end,
	)


def join(*commands: Command, timeout: int | None = None) -> list[Command]:
	"""Waits for the given commands, or all, up to `timeout`."""
	return Runner.Get().join(*commands, timeout=timeout)


def terminate(*commands: Command, graceful: bool = True) -> bool:
	"""Terminates the given commands, or all, gracefully by default."""
	return Runner.Get().terminate(*commands, graceful=graceful)


def cli(argv: list[str] | str = sys.argv[1:]) -> None:
	"""The command-line interface of this module."""
	CLI.Main(argv)


if __name__ == "__main__":
	cli()
# EOF
