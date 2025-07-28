#!/usr/bin/env sh
python3 -m multiplex "A=python3 -m http.server" "+A=ab -n1000 http://localhost:8000/"
# EOF
