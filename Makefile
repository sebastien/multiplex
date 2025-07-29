SHELL:= bash
.SHELLFLAGS:= -eu -o pipefail -c
MAKEFLAGS+= --warn-undefined-variables
MAKEFLAGS+= --no-builtin-rules
PROJECT:=multiplex
PYPI_PROJECT=multiplex-sh
VERSION:=$(shell grep VERSION setup.py  | head -n1 | cut -d '"' -f2)

PYTHON=python
PATH_SOURCES_PY=src/py
PYTHON_MODULES=$(patsubst src/py/%,%,$(wildcard src/py/*))
SOURCES_BIN:=$(wildcard bin/*)
SOURCES_PY:=$(wildcard $(PATH_SOURCES_PY)/*.py $(PATH_SOURCES_PY)/*/*.py $(PATH_SOURCES_PY)/*/*/*.py $(PATH_SOURCES_PY)/*/*/*/*.py)
MODULES_PY:=$(filter-out %/__main__,$(filter-out %/__init__,$(SOURCES_PY:$(PATH_SOURCES_PY)/%.py=%)))

PATH_LOCAL_PY=$(firstword $(shell python -c "import sys,pathlib;sys.stdout.write(' '.join([_ for _ in sys.path if _.startswith(str(pathlib.Path.home()))] ))"))
PATH_LOCAL_BIN=$(HOME)/.local/bin

REQUIRE_PY=flake8 bandit mypy twine
PREP_ALL=$(REQUIRE_PY:%=build/require-py-%.task)
# Commands
BANDIT=$(PYTHON) -m bandit
FLAKE8=$(PYTHON) -m flake8
MYPY=$(PYTHON) -m mypy
TWINE=$(PYTHON) -m twine
MYPYC=mypyc

cmd-check=if ! $$(which $1 &> /dev/null ); then echo "ERR Could not find command $1"; exit 1; fi; $1

.PHONY: prep
prep: $(PREP_ALL)
	@

.PHONY: run
run:
	@

.PHONY: ci
ci: check test
	@

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
	COMPILED=$$(PYTHONPATH=build python -c "import $(PROJECT);print($(PROJECT))")
	echo "Extra compiled at: $$COMPILED"

.PHONY: check-bandit
check-bandit: $(PREP_ALL)
	@echo "=== $@"
	$(BANDIT) -r -s B101 src/py/coda

.PHONY: check-flakes
check-flakes: $(PREP_ALL)
	@echo "=== $@"
	$(FLAKE8) --ignore=E1,E203,E231,E302,E401,E501,E704,E741,E266,F821,W  $(SOURCES_PY)

.PHONY: check-mypyc
check-mypyc: $(PREP_ALL)
	@$(call cmd-check,mypyc)  $(SOURCES_PY)

.PHONY: check-strict
check-strict: $(PREP_ALL)
	@
	count_ok=0
	count_err=0
	files_err=
	for item in $(SOURCES_PY); do
		if $(MYPY) --strict $$item; then
			count_ok=$$(($$count_ok+1))
		else
			count_err=$$(($$count_err+1))
			files_err+=" $$item"
		fi
	done
	summary="OK $$count_ok ERR $$count_err TOTAL $$(($$count_err + $$count_ok))"
	if [ "$$count_err" != "0" ]; then
		for item in $$files_err; do
			echo "ERR $$item"
		done
		echo "EOS FAIL $$summary"
		exit 1
	else
		echo "EOS OK $$summary"
	fi

.PHONY: lint
lint: check-flakes
	@

.PHONY: format
format:
	@ruff $(SOURCES_PY)

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

build/require-py-%.task:
	@
	if $(PYTHON) -mpip install --user --upgrade '$*'; then
		mkdir -p "$(dir $@)"
		touch "$@"
	fi

print-%:
	$(info $*=$($*))

.ONESHELL:

# EOF
