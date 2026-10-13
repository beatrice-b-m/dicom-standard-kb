.PHONY: install check format lint typecheck test test-integration \
	ingest-fixture run-mcp

UV_RUN = uv run --locked --all-extras --dev
EDITION ?= 2026b

install:
	uv sync --locked --all-extras --dev

check: lint typecheck test

format:
	$(UV_RUN) ruff format .

lint:
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .

typecheck:
	$(UV_RUN) mypy

test:
	$(UV_RUN) pytest tests/unit

test-integration:
	$(UV_RUN) pytest tests/integration_requires_dicom_download

ingest-fixture:
	$(UV_RUN) dicom-kb build-fixture

run-mcp:
	$(UV_RUN) dicom-kb mcp serve --edition $(EDITION)
