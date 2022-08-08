SOURCES_PY=$(wildcard src/py/*.py tests/*.py)
SOURCES_CELLS_PY:=$(shell grep '# --' $(SOURCES_PY) | cut -d: -f1 | sort | uniq)

PRODUCT_MD=$(SOURCES_CELLS_PY:%.py=docs/%.md)
PRODUCT_HTML=$(PRODUCT_MD:docs/%.md=site/%.html)
PRODUCT=$(PRODUCT_MD) $(PRODUCT_HTML)

BIN_CELLS:=.deps/cells/bin/cells
BIN_TEXTO:=.deps/texto/bin/texto

PYTHONPATH:=.deps/cells/src/py:.deps/texto/src:$(PYTHONPATH)
export PYTHONPATH


all: deps $(PRODUCT)

deps: .deps/cells .deps/texto

check:
	bandit -sB101 $(SOURCES_PY)
	pyflakes $(SOURCES_PY)


clean: $(PRODUCT)
	@for FILE in $(PRODUCT); do if [ -f "$$FILE" ]; then unlink "$$FILE"; fi; done

docs/%.md: %.py
	mkdir -p $(dir $@)
	$(BIN_CELLS) fmt -tmd -o $@ $<

site/%.html: docs/%.md
	mkdir -p $(dir $@)
	echo "<html><body>" > $@
	$(BIN_TEXTO) -thtml $< >> $@
	echo "</body></html>" >> $@

.deps/cells:
	mkdir -p $(dir $@)
	git clone https://github.com/sebastien/cells.git "$@"

.deps/texto:
	mkdir -p $(dir $@)
	git clone https://github.com/sebastien/texto.git "$@"


PHONY: all deps

# EOF
