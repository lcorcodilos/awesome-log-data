"""Shared archive-extraction helper used by adapters at discover() time.

Extraction is persistent (a sibling directory next to the archive), not a
temp dir, so RecordParser.resolve() keeps working against the same path
later — not just during the discover() call that first extracted it.
"""

from __future__ import annotations

import gzip
import shutil
import tarfile
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


def extract_tar(tar_path: Path, dest_dir: Path | None = None) -> list[Path]:
    """Extract every member of tar_path into dest_dir (default: a sibling
    directory named after the tar, extension stripped), unless dest_dir
    already exists (assumed to hold a complete extraction from a prior
    run). Returns the extracted file paths."""
    if dest_dir is None:
        dest_dir = tar_path.with_suffix("")
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True)
        with tarfile.open(tar_path) as tf:
            tf.extractall(dest_dir, filter="data")
    return [p for p in dest_dir.rglob("*") if p.is_file()]


def gunzip(gz_path: Path, dest_path: Path | None = None) -> Path:
    """Decompress a single .gz file into dest_path (default: a sibling
    path with the .gz suffix stripped), unless dest_path already exists."""
    if dest_path is None:
        dest_path = gz_path.with_suffix("")
    if not dest_path.exists():
        with gzip.open(gz_path, "rb") as src, open(dest_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
    return dest_path
