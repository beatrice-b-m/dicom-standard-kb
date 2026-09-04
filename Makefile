.PHONY: install check format lint typecheck test test-integration \
	test-dicom-integration test-dicom-current test-dicom-release \
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
	$(UV_RUN) pytest tests/unit tests/agent_regression

test-integration:
	$(UV_RUN) pytest tests/integration_requires_dicom_download

test-dicom-integration: test-integration

test-dicom-current:
	DICOM_KB_RUN_CURRENT=1 $(UV_RUN) pytest -m dicom_current tests/integration_requires_dicom_download/test_current_resolution.py

test-dicom-release:
	DICOM_KB_RUN_RELEASE=1 $(UV_RUN) pytest -m dicom_release tests/integration_requires_dicom_download/test_release_gate.py tests/integration_requires_dicom_download/test_release_goldens.py

ingest-fixture:
	$(UV_RUN) dicom-kb build-fixture

run-mcp:
	$(UV_RUN) dicom-kb mcp serve --edition $(EDITION)
