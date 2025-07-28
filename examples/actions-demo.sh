#!/usr/bin/env bash
# Actions example: demonstrating |silent, |end, and other actions
PYTHON="${PYTHON:-python3}"
echo "Running actions example..."
echo "SERVER will run silently, TEST will end all processes when complete"
$PYTHON -m multiplex \
    "SERVER|silent=echo 'Server starting...'; sleep 10; echo 'Server stopped'" \
    "+1=echo 'Running tests against silent server...'" \
    "+2|end=echo 'Tests completed - ending all processes'"