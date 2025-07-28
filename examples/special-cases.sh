#!/usr/bin/env bash
# Special cases example: commands with equals signs and complex patterns
PYTHON="${PYTHON:-python3}"
echo "Running special cases example..."
echo "Demonstrating commands with equals signs and complex patterns"
$PYTHON -m multiplex \
    "=echo 'Setting VAR=value'" \
    "+1=echo 'Command with spaces and special chars: a=b c=d'" \
    "SETUP+0.5|silent=echo 'Silent setup process'" \
    "+SETUP=echo 'Setup completed, continuing...'"