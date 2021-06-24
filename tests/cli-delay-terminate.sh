# NOTE: this should terminate as soon as `ab` ends
time python src/py/multiplex.py  'python -m http.server' '+1|end=ab -n10000 http://localhost:8000/'
# EOF
