from multiplex import run, terminate
import time
# --
# Tests the proper termination of a long-running process. Note that watch does
# refresh the terminal, so it does not do a full re-render.
count = 0


def on_date(command, data):
	global count
	print(f"Iteration {count}")
	count += 1


run("watch", "-n1", "date", onOut=on_date)
time.sleep(5)
terminate()
assert count == 6
print("OK")
# EOF
