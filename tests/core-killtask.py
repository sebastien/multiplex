import os
import select
import signal
import time
from typing import Optional
from subprocess import Popen, PIPE
from threading import Thread


# --
# This exercises the ability to kill a process and a thread reading from the
# process. This is a core mechanim used by `multiplex`.
PID = None


def run():
	global PID
	process = Popen(["watch", "-n1", "date"], stdout=PIPE, stderr=PIPE, bufsize=0)
	PID = process.pid
	channels = [process.stdout.fileno()]
	while True:
		try:
			for fd in select.select(channels, [], [])[0]:
				chunk = os.read(fd, 64_000)
				if chunk:
					pass
				else:
					os.close(fd)
					break
		except OSError:
			break


def check_pid(pid: Optional[int]):
	if pid == None:
		return False
	try:
		os.kill(pid, 0)
	except OSError:
		return False
	return True


thread = Thread(target=run, args=())
thread.start()
thread_pid = thread.native_id
# We wait a bit
time.sleep(0.1)
assert check_pid(os.getpid())
assert check_pid(thread_pid)
assert check_pid(PID)
time.sleep(2)
os.kill(PID, signal.SIGINT)
time.sleep(0.1)
assert not check_pid(PID)
thread.join()
time.sleep(0.1)
assert not check_pid(thread_pid)

print("OK")
# EOF
