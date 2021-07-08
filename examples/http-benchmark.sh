#!/usr/bin/env sh
python -m multiplex "A=python -m http.server" "+A=ab -n1000 http://localhost:8000/"
