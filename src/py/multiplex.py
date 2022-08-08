#!/usr/bin/env python
from typing import Optional, Callable, Union, NamedTuple, Iterable
from threading import Thread
from pathlib import Path
import re
import subprocess
import select
import signal
import os
import sys
import time
import argparse

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

BytesConsumer = Callable[[bytes], None]
StartCallback = Callable[["Command"], None]
OutCallback = Callable[["Command", bytes], None]
ErrCallback = Callable[["Command", bytes], None]
EndCallback = Callable[["Command", int], None]
DataCallback = Callable[["Command", bytes], None]


def SwallowStart(command: "Command"):
    pass


def SwallowOut(command: "Command", data: bytes):
    pass


def SwallowErr(command: "Command", data: bytes):
    pass


def SwallowEnd(command: "Command", data: int):
    pass


RE_PID = re.compile(r"(\d+)")


def shell(command: list[str], input: Optional[bytes] = None) -> Optional[bytes]:
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
    def parent(pid: int) -> Optional[int]:
        path = Path(f"/proc/{pid}/stat", "rt")
        return int(path.read_text().split()[3]) if path.exists() else None

    @staticmethod
    def exists(pid: int) -> bool:
        return Path(f"/proc/{pid}").exists()

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
        except OSError as e:
            return False

    @classmethod
    def killchild(cls, pid: int) -> bool:
        return cls.kill(pid)

    @classmethod
    def mem(cls, pid: int) -> tuple[str, str]:
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


# def audit(event: str, data: tuple):
#     print(f"Audit: {event} -> {data}")
#
#
# sys.addaudithook(audit)


class Command:
    """Represents a system command"""

    def __init__(self, args: list[str], key: str, pid: Optional[int] = None):
        self.key = key
        self.args = args
        self.pid = pid
        self._children: set[int] = set()
        # Callbacks
        self.onStart: list[Optional[StartCallback]] = []
        self.onOut: list[Optional[OutCallback]] = []
        self.onErr: list[Optional[ErrCallback]] = []
        self.onEnd: list[Optional[EndCallback]] = []

    # TODO: We may want to have a recursive subprocess listing
    @property
    def children(self) -> set[int]:
        if self.pid:
            self._children = self._children.union(Proc.children(self.pid))
        return self._children

    @property
    def ppid(self) -> Optional[int]:
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

    def silent(self):
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
        writer: Optional[Callable[[bytes], None]] = lambda data: None
        if os.write(1, data)
        else None,
    ):
        self.writer = writer

    def start(self, command: Command):
        return self.format(
            "start", command.key, bytes(" ".join(str(_) for _ in command.args), "utf8")
        )

    def out(self, command: Command, data: bytes):
        return self.format("out", command.key, data, self.SEP)

    def err(self, command: Command, data: bytes):
        return self.format("err", command.key, data, self.SEP)

    def end(self, command: Command, data: int):
        return self.format("end", command.key, data, self.SEP)

    def format(self, stream: str, key: str, data: Union[int, bytes], sep: str = SEP):
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
    Instance: Optional["Runner"] = None

    @classmethod
    def Get(cls) -> "Runner":
        if cls.Instance is None:
            cls.Instance = Runner()
        return cls.Instance

    def __init__(self):
        self.commands: dict[str, tuple[Command, Thread]] = {}
        self.formatter: Formatter = Formatter()
        self.registerSignals()

    def getActiveCommands(
        self, commands: Optional[dict[str, tuple[Command, Thread]]]
    ) -> dict[str, tuple[Command, Thread]]:
        """Returns the subset of commands that are active."""
        commands = commands or self.commands
        return dict((k, v) for k, v in commands.items() if v[1].is_alive())

    # --
    # ### Event dispatching
    #
    # This dispatches the events to the `formatter` first, and then to
    # the command's internal event handlers.

    def doStart(self, command: Command):
        if not command.onStart:
            self.formatter.start(command)
        else:
            for _ in command.onStart:
                _ and _(command)

    def doOut(self, command: Command, data: bytes):
        if not command.onOut:
            self.formatter.out(command, data)
        else:
            for _ in command.onOut:
                _ and _(command, data)

    def doErr(self, command: Command, data: bytes):
        if not command.onErr:
            self.formatter.err(command, data)
        else:
            for _ in command.onErr:
                _ and _(command, data)

    def doEnd(self, command: Command, data: int):
        if not command.onEnd:
            self.formatter.end(command, data)
        else:
            for _ in command.onEnd:
                _ and _(command, data)

    # --
    # ### Running, joining, terminating
    #
    # These are the key primitives that
    def run(
        self,
        command: list[str],
        key: Optional[str] = None,
        delay: Optional[float] = None,
        actions: Optional[list[str]] = None,
    ) -> Command:
        key = key or str(len(self.commands))
        cmd = Command(command, key)
        if actions and "silent" in actions:
            cmd.silent()
        # We create a process
        if delay:
            time.sleep(delay)
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

        def onEnd(data):
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
                lambda _: self.doOut(cmd, _),
                lambda _: self.doErr(cmd, _),
                onEnd,
            ),
        )
        thread.start()
        self.commands[key] = (cmd, thread)
        self.doStart(cmd)
        return cmd

    def reader_threaded(
        self,
        process: subprocess.Popen,
        out: Optional[BytesConsumer] = None,
        err: Optional[BytesConsumer] = None,
        end: Optional[Callable[[int], None]] = None,
    ):
        """A low-level, streaming blocking reader that calls back `out` and `err` consumers
        upon data."""
        # SEE: https://github.com/python/cpython/blob/3.9/Lib/subprocess.py
        channels = dict(
            (_[0].fileno(), _)
            for _ in ((process.stdout, out), (process.stderr, err))
            if _[0]
        )
        # NOTE: We could simply return the process here and do the multiplexing
        # in the select directly, but the intention is that the `run` command
        # is run in a thread. We use the low-level POSIX APIs in order to
        # do the minimum amount of buffering.
        while waiting := [_ for _ in channels]:
            for fd in select.select(waiting, [], [])[0]:
                chunk = os.read(fd, 64_000)
                if chunk:
                    if handler := channels[fd][1]:
                        handler(chunk)
                else:
                    os.close(fd)
                    del channels[fd]
        if end:
            end(process.returncode or 0)

    def join(self, *commands: Command, timeout: Optional[int] = None) -> list[Command]:
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
            left = timeout - elapsed if timeout else None
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

    def terminate(self, *commands: Command, resolution=0.1, timeout=5) -> bool:
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

    # --
    # ### Running, joining, terminating
    #
    # These are the key primitives that

    def registerSignals(self):
        for name, sig in self.SIGNALS.items():
            try:
                signal.signal(sig, self.onSignal)
            except OSError:
                # Maybe a Err
                pass
            except ValueError:
                # Signal not available there
                pass

    def onSignal(self, signum: int, frame):
        signame = next((k for k, v in self.SIGNALS.items() if v == signum), None)
        if signame == "SIGINT":
            self.terminate()
        elif signame == "SIGCHLD":
            pass


# --
# ##  API


def run(
    *args: Union[str, int],
    onStart: Optional[StartCallback] = None,
    onOut: Optional[OutCallback] = None,
    onErr: Optional[ErrCallback] = None,
    onEnd: Optional[EndCallback] = None,
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


def join(*commands: Command, timeout: Optional[int] = None):
    return Runner.Get().join(*commands, timeout=timeout)


def terminate():
    return Runner.Get().terminate()


def strip_ansi_bytes(data: bytes) -> bytes:
    return RE_ANSI_ESCAPE_8BIT.sub(b"", data)


def strip_ansi(data: str) -> str:
    return RE_ANSI_ESCAPE.sub("", data)


RE_LINE = re.compile(
    r"^((?P<key>[\dA-Za-z_]+)?(\+(?P<delay>\d+(\.\d+)?))?(?P<action>(\|[a-z]+)+)?=)?(?P<command>.+)$"
)


class ParsedCommand(NamedTuple):
    """Data structure holding a parsed command."""

    key: str
    delay: Optional[float]
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
    assert match
    key = match.group("key")
    delay = match.group("delay")
    command = match.group("command")
    actions = (match.group("action") or "").split("|")[1:]
    return ParsedCommand(
        key, float(delay) if delay else None, actions, [_ for _ in splitargs(command)]
    )


def cli(args=sys.argv[1:]):
    """The command-line interface of this module."""
    if type(args) not in (type([]), type(())):
        args = [args]
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
    args = oparser.parse_args(args=args)
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
