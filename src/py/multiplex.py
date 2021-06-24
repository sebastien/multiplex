#!/usr/bin/env python
from typing import List, Dict, Optional, Callable, Union, Tuple
from subprocess import Popen, PIPE
from threading import Thread
import re
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
    br'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])')
RE_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

BytesConsumer = Callable[[bytes], None]
StartCallback = Callable[['Command'], None]
OutCallback = Callable[['Command', bytes], None]
ErrCallback = Callable[['Command', bytes], None]
EndCallback = Callable[['Command', int], None]
DataCallback = Callable[['Command', bytes], None]


def SwallowStart(command: 'Command'): pass
def SwallowOut(command: 'Command', data: bytes): pass
def SwallowErr(command: 'Command', data: bytes): pass
def SwallowEnd(command: 'Command', data: int): pass


class Command:

    def __init__(self, args: List[str], key: str, pid: Optional[int] = None):
        self.key = key
        self.args = args
        self.pid = pid
        # Callbacks
        self.onStart: List[Optional[StartCallback]] = []
        self.onOut: List[Optional[OutCallback]] = []
        self.onErr: List[Optional[ErrCallback]] = []
        self.onEnd: List[Optional[EndCallback]] = []

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


class Formatter:
    """Formats a stream of events coming from a `Runner`."""

    SEP = "│"
    STREAMS = {
        "start": "$",
        "out": "<",
        "err": "!",
        "end": "=",
    }

    def __init__(self, writer: Optional[Callable[[bytes], None]] = lambda data: None if os.write(1, data) else None):
        self.writer = writer

    def start(self, command: Command):
        return self.format("start", command.key, bytes(" ".join(str(_) for _ in command.args), "utf8"))

    def out(self, command: Command, data: bytes):
        return self.format("out", command.key, data, self.SEP)

    def err(self, command: Command, data: bytes):
        return self.format("err", command.key, data, self.SEP)

    def end(self, command: Command, data: int):
        return self.format("end", command.key, data, self.SEP)

    def format(self, stream: str, key: str, data: Union[int, bytes], sep: str = SEP):
        prefix = bytes(f"{self.STREAMS[stream]}{sep}{key}{sep}", "utf8")
        lines = [bytes(str(data), "utf8")] if not isinstance(
            data, bytes) else data.split(b"\n")
        if isinstance(data, bytes) and data.endswith(b"\n"):
            lines = lines[:-1]
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

    Instance: Optional['Runner'] = None

    SIGNALS = dict((_, getattr(signal, _).value)
                   for _ in dir(signal) if _.startswith("SIG"))

    @classmethod
    def Get(cls) -> 'Runner':
        if cls.Instance is None:
            cls.Instance = Runner()
        return cls.Instance

    def __init__(self):
        self.commands: Dict[str, Tuple[Command, Thread]] = {}
        self.formatter: Formatter = Formatter()
        self.registerSignals()

    def getActiveCommands(self, commands: Optional[Dict[str, Tuple[Command, Thread]]]) -> Dict[str, Tuple[Command, Thread]]:
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
    def run(self, command: List[str], key: Optional[str] = None, delay: Optional[float] = None, actions: Optional[List[str]] = None) -> Command:
        key = key or str(len(self.commands))
        cmd = Command(command, key)
        # We create a process
        if delay:
            time.sleep(delay)
        process = Popen(command, stdout=PIPE, stderr=PIPE, bufsize=0)
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
                onEnd))
        thread.start()
        self.commands[key] = (cmd, thread)
        self.doStart(cmd)
        return cmd

    def reader_threaded(self, process: Popen, out: Optional[BytesConsumer] = None, err: Optional[BytesConsumer] = None, end: Optional[Callable[[int], None]] = None):
        """A low-level, streaming blocking reader that calls back `out` and `err` consumers
        upon data."""
        # SEE: https://github.com/python/cpython/blob/3.9/Lib/subprocess.py
        channels = dict((_[0].fileno(), _)
                        for _ in ((process.stdout, out), (process.stderr, err)))
        # NOTE: We could simply return the process here and do the multiplexing
        # in the select directly, but the intention is that the `run` command
        # is run in a thread. We use the low-level POSIX APIs in order to
        # do the minimum amount of buffering.
        while waiting := [_ for _ in channels]:
            for fd in select.select(waiting, [], [])[0]:
                chunk = os.read(fd, 64_000)
                if chunk:
                    if (handler := channels[fd][1]):
                        handler(chunk)
                else:
                    os.close(fd)
                    del channels[fd]
        if end:
            end(process.returncode or 0)

    def join(self, *commands: Command, timeout: Optional[int] = None) -> bool:
        """Joins all or the given list of commands, waiting indefinitely or up
        to the given `timeout` value."""
        selection = dict((k, v) for k, v in self.commands.items(
        ) if v[0] in commands) if commands else self.commands
        started = time.time()
        elapsed = 0
        while (active := self.getActiveCommands(selection)) and (timeout is None or elapsed < timeout):
            t = (timeout/len(active)) if timeout else None
            for _, thread in active.values():
                thread.join(timeout=t)
            elapsed = time.time() - started
        return not self.getActiveCommands(selection)

    def terminate(self, *commands: Command, resolution=0.1, timeout=5) -> bool:
        """Terminates given list of commands, waiting indefinitely or up
        to the given `timeout` value."""
        # We extract the commands the the corresponding threads
        selection = dict((k, v) for k, v in self.commands.items(
        ) if v[0] in commands) if commands else self.commands
        # Now we iterate and kill, the command processes, the threads will die
        # off accordingly.
        started = time.time()
        iteration = 0
        while selection:
            for cmd, _ in selection.values():
                if cmd.pid is not None:
                    try:
                        os.kill(
                            cmd.pid, self.SIGNALS["SIGHUP" if iteration == 0 else "SIGINT"])
                    except OSError:
                        pass
                    except ProcessLookupError:
                        pass
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
        signame = next(
            (k for k, v in self.SIGNALS.items() if v == signum), None)
        if signame == "SIGINT":
            self.terminate()
        elif signame == "SIGCHLD":
            pass

# --
# ##  API


def run(*args: Union[str, int],
        onStart: Optional[StartCallback] = None,
        onOut: Optional[OutCallback] = None,
        onErr: Optional[ErrCallback] = None,
        onEnd: Optional[EndCallback] = None,
        ) -> Command:
    command = Runner.Get().run([str(_) for _ in args])
    onStart and command.onStart.append(onStart)
    onOut and command.onOut.append(onOut)
    onErr and command.onErr.append(onErr)
    onEnd and command.onEnd.append(onEnd)
    return command


def join(*commands: Command, timeout: Optional[int] = None):
    return Runner.Get().join(*commands, timeout=timeout)


def terminate():
    return Runner.Get().terminate()


def strip_ansi_bytes(data: bytes) -> bytes:
    return RE_ANSI_ESCAPE_8BIT.sub(b'', data)


def strip_ansi(data: str) -> str:
    return RE_ANSI_ESCAPE.sub('', data)


RE_LINE = re.compile(
    r"^((?P<key>[\dA-Za-z_]+)?(\+(?P<delay>\d+(\.\d+)?))?(?P<action>(\|[a-z]+)+)?=)?(?P<command>.+)$")


def parse(line: str):
    match = RE_LINE.match(line)
    # TODO: Should be a bit more sophisticated
    assert match
    key = match.group("key")
    delay = match.group("delay")
    command = match.group("command")
    actions = (match.group("action") or "").split("|")[1:]
    return key, float(delay) if delay else None, actions, command.split()


def cli(args=sys.argv[1:]):
    """The command-line interface of this module."""
    if type(args) not in (type([]), type(())):
        args = [args]
    oparser = argparse.ArgumentParser(
        prog="multiplex",
    )
    # TODO: Rework command lines arguments, we want something that follows
    # common usage patterns.
    oparser.add_argument("commands", metavar="COMMANDS", type=str, nargs='+',
                         help='The list of commands to run in parallell')
    oparser.add_argument("-o", "--output",    type=str,  dest="output", default="-",
                         help="Specifies an output file")
    oparser.add_argument("-t", "--timeout",    type=int,  dest="timeout", default=0,
                         help="Specifies a timeout until which the commands are terinated")
    # We create the parse and register the options
    args = oparser.parse_args(args=args)
    out_path = args.output if args.output and args.output != "-" else None
    out = open(out_path, "wt") if out_path else sys.stdout
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
