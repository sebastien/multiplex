#!/usr/bin/env bash
# Sequential execution example: build then start
PYTHON="${PYTHON:-python3}"
echo "Running sequential build and start example..."
$PYTHON -m multiplex "BUILD=echo 'Building application...'" "+BUILD=echo 'Starting application...'"