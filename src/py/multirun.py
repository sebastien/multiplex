from typing import List, Optional, Callable
from enum import Enum
from subprocess import Popen, PIPE
from io import BytesIO
from threading import Thread
import sys
import contextlib
import select
import signal
import os


BytesConsumer = Callable[[bytes], None]


def run(command: List[str], out: Optional[BytesConsumer] = None, err: Optional[BytesConsumer] = None) -> int:
    # SEE: https://github.com/python/cpython/blob/3.9/Lib/subprocess.py
    assert command
    process = Popen(command, stdout=PIPE, stderr=PIPE, bufsize=0)
    channels = dict((_[0].fileno(), _)
                    for _ in ((process.stdout, out), (process.stderr, err)))
    while waiting := [_ for _ in channels]:
        for fd in select.select(waiting, [], [])[0]:
            chunk = os.read(fd, 64_000)
            if chunk:
                if (handler := channels[fd][1]):
                    handler(chunk)
            else:
                os.close(fd)
                del channels[fd]
    return process.returncode


SIGNALS = dict((_, getattr(signal, _).value)
               for _ in dir(signal) if _.startswith("SIG"))


class Runner:

    def __init__(self):
        self.threads = []
        self.registerSignals()

    def run(self, command: List[str]):
        def out(prefix):
            def writer(data: bytes):
                sys.stdout.write(f"{prefix}{str(data, 'utf8')}\n")
                sys.stdout.flush()
        n = len(self.threads)
        on_out = out(f">>>:{n}")
        on_err = out(f"!!!:{n}")
        t = Thread(target=run, args=(command, on_out, on_err))
        t.start()
        return self

    def join(self):
        for _ in self.threads:
            _.join()
        return self

    def registerSignals(self):
        for name, sig in SIGNALS.items():
            try:
                signal.signal(sig, self.onSignal)
            except OSError:
                # Maybe a Err
                pass
            except ValueError:
                # Signal not available there
                pass

    def onSignal(self, signum: int, frame):
        signame = next((k for k, v in SIGNALS.items() if v == signum), None)
        print("Got signal", signame)


if __name__ == "__main__":

    Runner().run(["python", "-m", "http.server"]).join()
    # run(["python", "-m", "http.server"])

    # run(["dmesg"])
# EOF
