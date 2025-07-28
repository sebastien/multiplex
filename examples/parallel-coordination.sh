#!/usr/bin/env bash
# Parallel coordination example: database, API, and UI startup
PYTHON="${PYTHON:-python3}"
echo "Running parallel coordination example..."
echo "Simulating: DB startup, API after 2s, UI after 2s, then browser after 5s"
$PYTHON -m multiplex \
    "DB=echo 'Starting database...'; sleep 3; echo 'Database ready'" \
    "API+2=echo 'Starting API server...'; sleep 2; echo 'API ready on port 8000'" \
    "UI+2=echo 'Starting UI server...'; sleep 2; echo 'UI ready on port 3000'" \
    "+5=echo 'Opening browser at http://localhost:3000'"