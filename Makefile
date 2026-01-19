VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

.PHONY: venv dev_deps build run test types lint check clean

venv:
	python3.13 -m venv $(VENV)
	$(PY) -m pip install -U pip

build:
	$(PIP) install -e .

dev_deps:
	$(PIP) install -e .[dev]



# Run to set up initally.
setup: venv dev_deps

run:
	$(VENV)/bin/agent-lib

test:
	$(VENV)/bin/pytest -q

types:
	$(VENV)/bin/pyright --level error

lint:
	$(VENV)/bin/ruff check . --select E,F,B --ignore E501

check: types test lint

clean:
	rm -rf .venv dist build *.egg-info .pytest_cache .ruff_cache __pycache__
