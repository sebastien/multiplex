from typing import Union
from multiplex import run, join, terminate, strip_ansi_bytes, Command
import re
import time

# --
# # Multiplexing API example
#
# We run a web server alongside CPU% and MEM% consumption and the Apache
# benchmark suite.


# We keep a global request counter
count = 0
expected_requests = 10_000


def parse_request(source: Command, data: bytes):
    """Whenever a request happens, we increase the counter and terminate once
    we've met the counter."""
    global count
    count += 1
    if count % 500 == 0:
        print(f"Requests performed: {count}, {100 * count/expected_requests}%")
    if count >= expected_requests:
        terminate()


def parse_cpu(source: Command, data: bytes):
    """Parses the CPU and MEM consumption as fed by `top`."""
    match = bytes(f"{server.pid}", "utf8")
    lines = [_ for _ in strip_ansi_bytes(data).split(b"\n") if match in _]
    stats = re.split(r"\s+", str(lines[-1], "utf8"))[1:-1] if lines else None
    if stats:
        pid, user, pr, ni, virt, res, shr, s, cpu, mem = stats[0:10]
        print(f"CPU:{cpu} MEM:{mem}")


server = run("python", "-m", "http.server", onErr=parse_request)
cpu = run("top", "-p", server.pid, onOut=parse_cpu)
time.sleep(2)
tester = run("ab", f"-n{expected_requests}", "http://localhost:8000/").silent()

started = time.time()
join(timeout=5)
print(f"join: {time.time() - started}s")

started = time.time()
terminate()
print(f"terminate: {time.time() - started}s")
print("OK")

# EOF
