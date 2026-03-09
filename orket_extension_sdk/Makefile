PYTHON ?= python

.PHONY: install test lint build publish-wheelhouse

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[testing]"

test:
	$(PYTHON) -m pytest -q ../tests/sdk/

lint:
	$(PYTHON) -m ruff check . ../tests/sdk/

build:
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build --sdist --wheel .

publish-wheelhouse: build
	@test -n "$(WHEELHOUSE)" || (echo "WHEELHOUSE is required"; exit 1)
	@mkdir -p "$(WHEELHOUSE)"
	@cp -f dist/* "$(WHEELHOUSE)/"
	@echo "Copied SDK artifacts to $(WHEELHOUSE)"
