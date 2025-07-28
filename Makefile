SHELL:=bash
.SHELLFLAGS:= -eu -o pipefail -c
MAKEFLAGS+= --warn-undefined-variables
MAKEFLAGS+= --no-builtin-rules

PYTHON=python3
PATH_SOURCES_PY=src/py
PYTHON_MODULES=$(patsubst src/py/%,%,$(wildcard src/py/*))
SOURCES_BIN:=$(wildcard bin/*)
SOURCES_PY:=$(wildcard $(PATH_SOURCES_PY)/*.py $(PATH_SOURCES_PY)/*/*.py $(PATH_SOURCES_PY)/*/*/*.py $(PATH_SOURCES_PY)/*/*/*/*.py)
MODULES_PY:=$(filter-out %/__main__,$(filter-out %/__init__,$(SOURCES_PY:$(PATH_SOURCES_PY)/%.py=%)))

PATH_LOCAL_PY=$(firstword $(shell python -c "import sys,pathlib;sys.stdout.write(' '.join([_ for _ in sys.path if _.startswith(str(pathlib.Path.home()))] ))"))
PATH_LOCAL_BIN=$(HOME)/.local/bin

REQUIRE_PY=flake8 bandit mypy
PREP_ALL=$(REQUIRE_PY:%=build/require-py-%.task)
# Commands
BANDIT=$(PYTHON) -m bandit
FLAKE8=$(PYTHON) -m flake8
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

	mkdir -p "build"
	$(foreach M,$(MODULES_PY),mkdir -p build/$M;)
	env -C build MYPYPATH=$(realpath .)/src/py mypyc -p multiplex

.PHONY: check
check: check-bandit check-flakes check-strict
	echo "=== $@"

.PHONY: check-compiled
check-compiled:
	@
	echo "=== $@"
	COMPILED=$$(PYTHONPATH=build python -c "import multiplex;print(multiplex)")
	echo "Extra compiled at: $$COMPILED"

.PHONY: check-bandit
check-bandit: $(PREP_ALL)
	@echo "=== $@"
	$(BANDIT) -r -s B101 src/py/coda

.PHONY: check-flakes
check-flakes: $(PREP_ALL)
	@echo "=== $@"
	$(FLAKE8) --ignore=E1,E203,E302,E401,E501,E704,E741,E266,F821,W  $(SOURCES_PY)

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
	@black $(SOURCES_PY)

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

data/csic_2010-normalTrafficTraining.txt:
	curl -o "$@" 'https://gitlab.fing.edu.uy/gsi/web-application-attacks-datasets/-/raw/master/csic_2010/normalTrafficTest.txt?inline=false'

data/csic_2010-anomalousTrafficTraining.txt:
	curl -o "$@" 'https://gitlab.fing.edu.uy/gsi/web-application-attacks-datasets/-/raw/master/csic_2010/anomalousTrafficTest.txt?inline=false'

print-%:
	$(info $*=$($*))

.ONESHELL:
# EOF
#
