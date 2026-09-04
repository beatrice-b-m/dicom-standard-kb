"""Shared query option declarations; defaults remain on command signatures."""

from pathlib import Path
from typing import Annotated

import typer

EditionOption = Annotated[
    str | None,
    typer.Option("--edition", help="Concrete DICOM edition label."),
]
DatabaseOption = Annotated[
    Path | None,
    typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
]
CacheDirectoryOption = Annotated[
    Path | None,
    typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
]
