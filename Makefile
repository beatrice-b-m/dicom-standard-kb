.PHONY: install lint typecheck test test-integration ingest-fixture run-mcp run-api

install:
	uv sync --all-extras --dev

lint:
	uv run --dev ruff check .

typecheck:
	uv run --dev mypy

test:
	uv run --dev pytest

test-integration:
	uv run --dev pytest tests/integration_requires_dicom_download

ingest-fixture:
	uv run --dev dicom-kb build-fixture

run-mcp:
	uv run --all-extras --dev dicom-kb mcp serve --edition 2026b

run-api:
	@echo "HTTP API is post-v1 optional and is not implemented yet."
