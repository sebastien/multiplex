# File: src/mk/config.mk
# Multiplex project configuration.

# -----------------------------------------------------------------------------
#
# CONFIGURATION
#
# -----------------------------------------------------------------------------

# --
# Python tests follow the pytest naming convention (loaded before the
# SDK rules are parsed, so `make test` picks them up).
TESTS_PY=$(wildcard tests/test_*.py)

# EOF
