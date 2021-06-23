from typing import List, Dict, Optional, Callable, Union, TypeVar, Generic, cast
from subprocess import Popen, PIPE
from threading import Thread
from io import BytesIO
import re
import select
import signal
import os
import time

# --
# Multiplex Command Multiplex
#
# The `multiplex` module implements a multiplexing command runner that allows
# for running multiple, potentially long running commands, merge their output
# a single output stream.


# --
# ## Types

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
        self.threads: Dict[str, Thread] = {}
        self.commands: Dict[str, Command] = {}
        self.formatter: Formatter = Formatter()
        self.registerSignals()

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
    def run(self, command: List[str]) -> Command:
        key = str(len(self.threads))
        cmd = Command(command, key)
        t = Thread(target=popen, args=(command,
                                       lambda _: self.doOut(cmd, _),
                                       lambda _: self.doErr(cmd, _),
                                       lambda _: self.doEnd(cmd, _)))
        t.start()
        cmd.pid = t.native_id
        self.threads[key] = t
        self.commands[key] = cmd
        self.doStart(cmd)
        return cmd

    def join(self, *comamnds: Command, timeout: Optional[int] = None) -> bool:
        started = time.time()
        elapsed = 0
        while (alive_count := len([_ for _ in self.threads.values() if _.is_alive()])) and (timeout is None or elapsed < timeout):
            t = (timeout/alive_count) if timeout else None
            print("TIMEOUT", t, timeout, alive_count)
            for _ in self.threads.values():
                _.join(timeout=t)
                # FIXME: We should indicate termination there
            elapsed = time.time() - started
        for t in self.threads.values():
            if t.is_alive():
                return False
        print("Joining")
        return True

    def terminate(self, resolution=0.1, timeout=5) -> bool:
        print("Termination started")
        started = time.time()
        iteration = 0
        while self.threads:
            # We try to stop the threads that are alive
            print("Terminating", self.threads)
            for _ in self.threads.values():
                if _.is_alive():
                    try:
                        res = os.kill(
                            _.native_id, self.SIGNALS["SIGHUP" if iteration == 0 else "SIGINT"])
                        print("RES=", res)
                    except ProcessLookupError as e:
                        # It's now dead
                        pass
            iteration += 1
            self.threads = dict((k, v)
                                for k, v in self.threads.items() if v.is_alive())
            # We exit early after the timeout
            elapsed = time.time() - started
            if elapsed >= timeout:
                return False
            if self.threads:
                time.sleep(resolution)
        print("Terminated", self.threads)
        return len(self.threads) == 0

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


def popen(command: List[str], out: Optional[BytesConsumer] = None, err: Optional[BytesConsumer] = None, end: Optional[Callable[[int], None]] = None) -> int:
    """A low-level, streaming blocking reader that calls back `out` and `err` consumers
    upon data."""
    # SEE: https://github.com/python/cpython/blob/3.9/Lib/subprocess.py
    assert command
    process = Popen(command, stdout=PIPE, stderr=PIPE, bufsize=0)
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
    return process.returncode


# FROM: https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
# 7-bit and 8-bit C1 ANSI sequences
RE_ANSI_ESCAPE_8BIT = re.compile(
    br'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])'
)

RE_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def strip_ansi_bytes(data: bytes) -> bytes:
    return RE_ANSI_ESCAPE_8BIT.sub(b'', data)


def strip_ansi(data: str) -> str:
    return RE_ANSI_ESCAPE.sub('', data)


if __name__ == "__main__":

    Runner().run(["python", "-m", "http.server"]
                 ).run(["date"]).join()
    # run(["python", "-m", "http.server"])

    # run(["dmesg"])
# EOF
