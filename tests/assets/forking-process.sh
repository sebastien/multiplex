#!/usr/bin/env bash
# --
# This script creates 5 subprocesses, that will be left orphaned, and reattached
# to the `systemd--user` process on most Linuxes. This is a good test case to see
# if multiplexing is able to catch these child processes and properly manage them.
FILE=$(readlink -f $0)
for i in 1 2 3 4 5; do
	echo "STEP Starting $i"
	watch -n1 du -hs "$FILE" & > /dev/null
done
echo "DONE"
# EOF
