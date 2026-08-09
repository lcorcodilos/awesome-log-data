"""Manifest module: source_id scheme, collision handling, JSONL read/write.

One row per source *file*, keyed by a deterministic source_id, so re-running
ingestion doesn't mint new IDs for files already catalogued.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel

from awesome_log_data.base import RecordRefType

logger = logging.getLogger(__name__)

_HASH_CHUNK_SIZE = 65536
_COLLISION_SUFFIX_LENGTH = 8
_ANSI_YELLOW = "\x1b[33m"
_ANSI_RESET = "\x1b[0m"


class ManifestEntry(BaseModel):
    source_id: str
    dataset_id: str
    file_name: str
    source_url: str
    license: str
    ingested_at: str
    checksum_sha256: str
    bytes: int
    record_count: int
    labeled: bool
    record_ref_type: RecordRefType
    notes: str


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class ManifestStore:
    """In-memory view of manifest.jsonl, keyed by source_id."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[str, ManifestEntry] = {}
        self.read()

    def get(self, source_id: str) -> ManifestEntry | None:
        return self._entries.get(source_id)

    def upsert(self, entry: ManifestEntry) -> None:
        self._entries[entry.source_id] = entry

    def __iter__(self) -> Iterator[ManifestEntry]:
        return iter(self._entries.values())

    def read(self) -> None:
        """(Re)load entries from disk, replacing whatever is in memory."""
        self._entries = {}
        if not self._path.exists():
            return
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                entry = ManifestEntry.model_validate_json(stripped)
                self._entries[entry.source_id] = entry

    def write(self, sort: bool = True) -> None:
        entries = list(self._entries.values())
        if sort:
            entries.sort(key=lambda e: e.source_id)
        with open(self._path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(entry.model_dump_json() + "\n")


def compute_source_id(
    dataset_id: str, file_name: str, file_path: Path, manifest: ManifestStore
) -> str:
    candidate = f"{dataset_id}/{file_name}"
    existing = manifest.get(candidate)
    if existing is None:
        return candidate
    new_checksum = sha256_file(file_path)
    if existing.checksum_sha256 == new_checksum:
        return candidate  # same file re-ingested, idempotent — not a real collision
    short_hash = new_checksum[:_COLLISION_SUFFIX_LENGTH]  # genuine collision — disambiguate
    disambiguated = f"{dataset_id}/{file_name}#{short_hash}"
    logger.warning(
        "%sfile_name collision for dataset %r, file_name %r — disambiguating as %r%s",
        _ANSI_YELLOW,
        dataset_id,
        file_name,
        disambiguated,
        _ANSI_RESET,
    )
    return disambiguated
