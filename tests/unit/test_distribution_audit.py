import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_TRACKED_PATH_PREFIXES = (
    "artifacts/",
    "generated-standard-json/",
    "generated-standard-text/",
    "vector-indexes/",
)
FORBIDDEN_TRACKED_SUFFIXES = (
    ".ann",
    ".db",
    ".duckdb",
    ".faiss",
    ".hnsw",
    ".html",
    ".htm",
    ".index",
    ".parquet",
    ".pdf",
    ".sqlite",
    ".sqlite3",
)
OFFICIAL_PART_XML_RE = re.compile(r"part\d{2}\.xml$")
FORBIDDEN_TRACKED_NAME_RES = (
    re.compile(r"standalone[-_]?terminology[-_]?dump", re.IGNORECASE),
    re.compile(r"terminology[-_]?dump", re.IGNORECASE),
    re.compile(r"context[-_]?group[-_]?export", re.IGNORECASE),
    re.compile(r"coded[-_]?concept[-_]?export", re.IGNORECASE),
    re.compile(r"code[-_]?meaning[-_]?export", re.IGNORECASE),
    re.compile(r"full[-_]?standard.*\.json$", re.IGNORECASE),
)


def _tracked_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def test_tracked_files_exclude_generated_official_artifacts() -> None:
    tracked_files = _tracked_files()

    forbidden_paths = [
        path
        for path in tracked_files
        if path.startswith(FORBIDDEN_TRACKED_PATH_PREFIXES)
        or path.endswith(FORBIDDEN_TRACKED_SUFFIXES)
        or OFFICIAL_PART_XML_RE.search(Path(path).name)
        or any(regex.search(Path(path).name) for regex in FORBIDDEN_TRACKED_NAME_RES)
    ]

    synthetic_xml = {
        path
        for path in tracked_files
        if path.startswith("tests/fixtures_synthetic/")
        and path.endswith("_docbook.xml")
    }
    xml_files = {path for path in tracked_files if path.endswith(".xml")}

    assert forbidden_paths == []
    assert xml_files == synthetic_xml


def test_package_and_docker_release_inputs_are_code_only() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert 'packages = ["src/dicom_kb"]' in pyproject
    assert "COPY src /app/src" in dockerfile

    for forbidden in (
        "COPY artifacts",
        "COPY generated-standard-json",
        "COPY generated-standard-text",
        "COPY vector-indexes",
        "*.sqlite",
        "*.db",
    ):
        assert forbidden not in dockerfile
