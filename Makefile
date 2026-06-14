.PHONY: install lint typecheck test test-integration test-dicom-integration test-dicom-current ingest-fixture run-mcp run-api

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

test-dicom-integration: test-integration

test-dicom-current:
	DICOM_KB_RUN_CURRENT=1 uv run --dev pytest -m dicom_current tests/integration_requires_dicom_download/test_current_resolution.py

ingest-fixture:
	uv run --dev dicom-kb build-fixture

run-mcp:
	uv run --all-extras --dev dicom-kb mcp serve --edition 2026b

run-api:
	@echo "HTTP API is post-v1 optional and is not implemented yet."
