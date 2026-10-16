.PHONY: test lint format-check typecheck verify

test:
	python -m pytest

lint:
	python -m ruff check .

format-check:
	python -m ruff format --check .

typecheck:
	python -m mypy

verify: lint format-check typecheck test
