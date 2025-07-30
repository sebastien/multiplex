
# --
# ## Make Version Detection & Enforcement

# Detect if we're running under GNU Make
MAKE_VERSION := $(shell $(MAKE) --version 2>/dev/null | head -1)
IS_GMAKE := $(if $(findstring GNU Make,$(MAKE_VERSION)),1,0)

# If not GNU Make, check for gmake and provide guidance
ifneq ($(IS_GMAKE),1)
  GMAKE_AVAILABLE := $(shell which gmake 2>/dev/null)
  ifneq ($(GMAKE_AVAILABLE),)
    $(error This Makefile requires GNU Make. Please run: gmake $(MAKECMDGOALS))
  else
    $(error This Makefile requires GNU Make. Please install it: brew install make (macOS) or apt-get install make (Linux), then run: gmake $(MAKECMDGOALS))
  endif
endif

# --
# ## Make & Shell Configuration

SHELL:= bash
.SHELLFLAGS:= -eu -o pipefail -c
MAKEFLAGS+= --warn-undefined-variables
MAKEFLAGS+= --no-builtin-rules

# --
# ## Project Configuration
PROJECT:=multiplex
PYPI_PROJECT=multiplex-sh
VERSION:=$(shell grep VERSION setup.py  | head -n1 | cut -d '"' -f2)

# --
# ## Python Configuration

PYTHON=python3
PYTHON_MODULES=$(patsubst src/py/%,%,$(wildcard src/py/*))
PYTHON_MODULES_PIP=ruff bandit mypy flake8
PATH_PYTHON_LIB=run/lib/python
PYTHONPATH:=$(abspath $(PATH_PYTHON_LIB)$(if $(PYTHONPATH),:$(PYTHONPATH)))
export PYTHONPATH

# --
# ## Sources Configuration

SOURCES_BIN:=$(wildcard bin/*)
SOURCES_PY_PATH=src/py
SOURCES_PY:=$(wildcard $(SOURCES_PY_PATH)/*.py $(SOURCES_PY_PATH)/*/*.py $(SOURCES_PY_PATH)/*/*/*.py $(SOURCES_PY_PATH)/*/*/*/*.py)
MODULES_PY:=$(filter-out %/__main__,$(filter-out %/__init__,$(SOURCES_PY:$(SOURCES_PY_PATH)/%.py=%)))

PATH_LOCAL_PY=$(firstword $(shell $(PYTHON) -c "import sys,pathlib;sys.stdout.write(' '.join([_ for _ in sys.path if _.startswith(str(pathlib.Path.home()))] ))"))
PATH_LOCAL_BIN=$(HOME)/.local/bin

PREP_ALL=$(PYTHON_MODULES_PIP:%=build/py-install-%.task)

# --
# ## Commands

BANDIT=$(PYTHON) -m bandit
FLAKE8=$(PYTHON) -m flake8
MYPY=$(PYTHON) -m mypy
TWINE=$(PYTHON) -m twine
MYPYC=mypyc

cmd-check=if ! $$(which $1 &> /dev/null ); then echo "ERR Could not find command $1"; exit 1; fi; $1

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  prep           - Install required Python modules"
	@echo "  test           - Run all tests"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-color     - Run color tests only"
	@echo "  test-dependencies - Run dependency tests only"
	@echo "  test-dependency-delays - Run dependency delay tests only"
	@echo "  test-process-start - Run process start dependency tests only"
	@echo "  test-examples  - Test dependency functionality with examples"
	@echo "  check          - Run all code quality checks"
	@echo "  check-bandit   - Run security audit with bandit"
	@echo "  check-flakes   - Run flake8 linting"
	@echo "  check-strict   - Run strict mypy type checking"
	@echo "  lint           - Run linting (alias for check-flakes)"
	@echo "  fmt            - Format code with ruff"
	@echo "  ci             - Run check and test (CI pipeline)"
	@echo "  audit          - Run security audit"
	@echo "  install        - Install to local Python environment"
	@echo "  release        - Build and release to PyPI"

.PHONY: prep
prep: $(PREP_ALL)
	@

.PHONY: run
run:
	@

.PHONY: ci
ci: check test
	@

.PHONY: test
test:
	@echo "=== Running tests ==="
	@echo "Running unit parse tests..."
	@$(PYTHON) tests/unit-parse.py
	@echo ""
	@echo "Running color tests..."
	@$(PYTHON) tests/test-color.py
	@echo ""
	@echo "Running dependency feature tests..."
	@$(PYTHON) tests/feature-dependencies.py
	@echo ""
	@echo "Running dependency delay tests..."
	@$(PYTHON) tests/feature-dependency-delays.py
	@echo ""
	@echo "Running process start dependency tests..."
	@$(PYTHON) tests/test-process-start-dependency.py
	@echo ""
	@echo "✅ All tests completed successfully!"

.PHONY: test-unit
test-unit:
	@echo "=== Running unit tests ==="
	@$(PYTHON) tests/unit-parse.py

.PHONY: test-color
test-color:
	@echo "=== Running color tests ==="
	@$(PYTHON) tests/test-color.py

.PHONY: test-dependencies
test-dependencies:
	@echo "=== Running dependency tests ==="
	@$(PYTHON) tests/feature-dependencies.py

.PHONY: test-dependency-delays
test-dependency-delays:
	@echo "=== Running dependency delay tests ==="
	@$(PYTHON) tests/feature-dependency-delays.py

.PHONY: test-process-start
test-process-start:
	@echo "=== Running process start dependency tests ==="
	@$(PYTHON) tests/test-process-start-dependency.py

.PHONY: test-examples
test-examples:
	@echo "=== Testing examples ==="
	@echo "Testing basic dependency functionality..."
	@$(PYTHON) src/py/multiplex.py "A=echo 'Process A started'" ":A=echo 'Waiting for A to finish'" ":A+1s|end=echo 'A finished, waited 1s'"
	@echo ""
	@echo "Examples test completed!"

.PHONY: audit
audit: check-bandit
	@echo "=== $@"

# NOTE: The compilation seems to create many small modules instead of a big single one
.PHONY: compile
compile:
	@echo "=== $@"
	echo "Compiling $(MODULES_PY): $(SOURCES_PY)"
	# NOTE: Output is going to be like '$(PROJECT)/__init__.cpython-310-x86_64-linux-gnu.so'
	mkdir -p "build"
	$(foreach M,$(MODULES_PY),mkdir -p build/$M;)
	env -C build MYPYPATH=$(realpath .)/src/py mypyc -p $(PROJECT)

.PHONY: check
check: check-bandit check-flakes check-strict
	echo "=== $@"

.PHONY: check-compiled
check-compiled:
	@
	echo "=== $@"
	COMPILED=$$(PYTHONPATH=build $(PYTHON) -c "import $(PROJECT);print($(PROJECT))")
	echo "Extra compiled at: $$COMPILED"

.PHONY: check-bandit
check-bandit: $(PREP_ALL)
	@echo "=== $@"
	$(BANDIT) -r -s B101 $(wildcard src/py/*)

.PHONY: check-flakes
check-flakes: $(PREP_ALL)
	@echo "=== $@"
	$(FLAKE8) --ignore=E1,E203,E231,E302,E401,E501,E704,E741,E266,F821,W  $(SOURCES_PY)

.PHONY: check-mypyc
check-mypyc: $(PREP_ALL)
	@$(call cmd-check,mypyc)  $(SOURCES_PY)

.PHONY: check-strict
check-strict: $(PREP_ALL)
	@count_ok=0;
	count_err=0;
	files_err="";
	for ITEM in $(SOURCES_PY); do
		if $(MYPY) --strict $$ITEM; then
			count_ok=$$(($$count_ok+1))
		else
			count_err=$$(($$count_err+1))
			files_err+=" $$ITEM"
		fi
	done
	summary="OK $$count_ok ERR $$count_err TOTAL $$(($$count_err + $$count_ok))"
	if [ "$$count_err" != "0" ]; then
		if [ -n "$$files_err" ]; then
			for item in $$files_err; do
				echo "ERR $$item"
			done
		fi
		echo "EOS FAIL $$summary"
		exit 1
	else
		echo "EOS OK $$summary"
	fi

.PHONY: lint
lint: check-flakes
	@

.PHONY: fmt
fmt:
	@$(PYTHON) -m ruff format #$(SOURCES_PY)

.PHONY: release-prep
release-prep: $(PREP_ALL)
	@
	# git commit -a -m "[Release] $(PROJECT): $(VERSION)"; true
	# git tag $(VERSION); true
	# git push --all; true

.PHONY: release
release: $(PREP_ALL)
	@
	$(PYTHON) setup.py clean sdist bdist_wheel
	$(TWINE) upload dist/$(subst -,_,$(PYPI_PROJECT))-$(VERSION)*

.PHONY: install
install:
	@for file in $(SOURCES_BIN); do
		echo "Installing $(PATH_LOCAL_BIN)/$$(basename $$file)"
		ln -sfr $$file "$(PATH_LOCAL_BIN)/$$(basename $$file)"
		mkdir -p "$(PATH_LOCAL_BIN)"
	done
	if [ ! -e "$(PATH_LOCAL_PY)" ]; then
		mkdir -p "$(PATH_LOCAL_PY)"
	fi
	if [ -d "$(PATH_LOCAL_PY)" ]; then
		for module in $(PYTHON_MODULES); do
			echo "Installing $(PATH_LOCAL_PY)/$$module"
			ln -sfr src/py/$$module "$(PATH_LOCAL_PY)"/$$module
		done
	else
		echo "No local Python module path found:  $(PATH_LOCAL_PY)"
	fi


.PHONY: try-install
try-uninstall:
	@for file in $(SOURCES_BIN); do
		unlink $(PATH_LOCAL_BIN)/$$(basename $$file)
	done
	if [ -s "$(PATH_LOCAL_PY)" ]; then
		for module in $(PYTHON_MODULES); do
			unlink "$(PATH_LOCAL_PY)"/$$module
		done
	fi

build/py-install-%.task:
	@
	# Remove task file if it's older than 7 days to force weekly updates
	if [ -f "$@" ] && [ $$(find "$@" -mtime +7 | wc -l) -gt 0 ]; then
		echo "Refreshing $* (task file older than 7 days)";
		rm -f "$@";
	fi
	mkdir -p "$(PATH_PYTHON_LIB)"
	if $(PYTHON) -mpip install --target="$(PATH_PYTHON_LIB)" --upgrade '$*'; then
		mkdir -p "$(dir $@)"
		touch "$@"
	fi

print-%:
	$(info $*=$($*))

.ONESHELL:
# EOF
