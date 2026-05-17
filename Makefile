PYTHON := python3

lint:
	ruff check .

format:
	ruff format .

type-check:
	mypy .

test:
	pytest

all: lint type-check test

.PHONY: lint format type-check test all
