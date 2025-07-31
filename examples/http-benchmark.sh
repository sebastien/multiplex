#!/usr/bin/env bash
PYTHON="${PYTHON:-python3}"
$PYTHON -m multiplex "A=python3 -m http.server" ":A=ab -n1000 http://localhost:8000/"
# EOF
