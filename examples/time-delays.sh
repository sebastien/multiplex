#!/usr/bin/env bash
# Time-based delays example: demonstrating different delay patterns including complex combinations
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Running time-based delays example with enhanced suffix support..."
echo "Commands will run at: immediate, +500ms, +2s, +1m, +1m30s750ms (90.75s)"
$PYTHON "$SCRIPT_DIR/../src/py/multiplex.py" \
    "echo 'Command 1: Starting immediately'" \
    "+500ms=echo 'Command 2: Started after 500 milliseconds'" \
    "+2s=echo 'Command 3: Started after 2 seconds'" \
    "+1m=echo 'Command 4: Started after 1 minute'" \
    "+1m30s750ms=echo 'Command 5: Complex timing - 90.75 seconds'"