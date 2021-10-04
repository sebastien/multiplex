from multiplex import run, terminate, Proc
from pathlib import Path
import time

# --
# Tests the proper termination of a process that creates many descendants
# and that does an early quit.
count = 0
BASE = Path(__file__).parent
cmd = str(BASE / "assets" / "forking-process.sh")
print(f"-- TEST forking: {cmd}")
process = run(cmd, onOut=lambda c, d: None)
print(f"   pid: {process.pid}")
print(f"   children: {process.children}")
all_pids = set([process.pid]).union(process.children)
for pid in all_pids:
    print(f"-- TEST pid active: {pid}")
    print(".. OK" if Proc.exists(pid) else "!! FAIL")
terminate()
for pid in all_pids:
    print(f"-- TEST pid terminated: {pid}")
    print("!! FAIL" if Proc.exists(pid) else ".. OK")
print("DONE")
# EOF
