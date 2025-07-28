#!/usr/bin/env bash
# Time-based delays example: demonstrating different delay patterns
PYTHON="${PYTHON:-python3}"
echo "Running time-based delays example..."
echo "Commands will run at: immediate, +1s, +2.5s, +4s"
$PYTHON -m multiplex \
    "echo 'Command 1: Starting immediately'" \
    "+1=echo 'Command 2: Started after 1 second'" \
    "+2.5=echo 'Command 3: Started after 2.5 seconds'" \
    "+4=echo 'Command 4: Started after 4 seconds'"