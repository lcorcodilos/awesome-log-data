"""Shared archive-extraction helper used by adapters at discover() time.

Extraction is persistent (a sibling directory next to the archive), not a
temp dir, so RecordParser.resolve() keeps working against the same path
later — not just during the discover() call that first extracted it.
"""

from __future__ import annotations

import zipfile
from pathlib import Path


def extract_zip(zip_path: Path, dest_dir: Path | None = None) -> list[Path]:
    """Extract every member of zip_path into dest_dir (default: a sibling
    directory named after the zip, extension stripped), unless dest_dir
    already exists (assumed to hold a complete extraction from a prior
    run). Returns the extracted file paths."""
    if dest_dir is None:
        dest_dir = zip_path.with_suffix("")
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest_dir)
    return [p for p in dest_dir.rglob("*") if p.is_file()]
