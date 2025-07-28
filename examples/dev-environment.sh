#!/usr/bin/env bash
# Development environment example: multi-service coordination
PYTHON="${PYTHON:-python3}"
echo "Running development environment simulation..."
echo "Starting: Database -> API (after 2s) -> UI (after 2s) -> Browser (after 5s)"
$PYTHON -m multiplex \
    "DB=echo 'MongoDB starting...'; sleep 2; echo 'MongoDB ready on port 27017'" \
    "API+2=echo 'Node.js API starting...'; sleep 1; echo 'API server ready on port 8000'" \
    "UI+2=echo 'React UI starting...'; sleep 1; echo 'UI server ready on port 3000'" \
    "+5=echo 'Development environment ready - opening http://localhost:3000'"