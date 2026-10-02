# AGENTS.md - Development Guidelines

## Build/Test/Lint Commands
- **Run all tests**: `make test` (pytest; config in `pytest.ini`)
- **Run single test**: `pytest tests/test_<name>.py` or `pytest -k <name>`
- **Lint**: `make lint` or `make check-flakes`
- **Type check**: `make check-strict` (mypy --strict + ruff F,I)
- **Format code**: `make fmt`
- **Full CI**: `make ci` (runs check + test)
- **Install deps**: `make prep`

## Code Style Guidelines
- **Language**: Python 3.12+ (use `from __future__ import annotations`)
- **Imports**: Standard library first, then third-party, group related imports
- **Types**: Use type hints with modern syntax (`type BytesConsumer = Callable[[bytes], None]`)
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants
- **Error handling**: Use exceptions, not return codes
- **Documentation**: Use docstrings for public functions, inline comments sparingly
- **Security**: Use `# nosec` comments when subprocess usage is intentional
- **Testing**: Tests go in `tests/` directory, use descriptive function names with `test_` prefix

## Project Structure
- Main module: `src/py/multiplex.py`
- Tests: `tests/test_*.py` (pytest, `pythonpath=src/py`); shared fixtures in `tests/conftest.py`
- Binary: `bin/multiplex`