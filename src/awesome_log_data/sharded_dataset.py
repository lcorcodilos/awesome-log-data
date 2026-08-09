"""Shards parsed records as JSONL across fixed-size files within a directory,
maintaining a flat JSONL index (global row -> shard file + byte offset +
source_id) for random access into a large parsed corpus without loading it
into memory. Write with append(), read with len()/[]/indices_for_source().

This complements, not replaces, RecordParser.resolve() (base.py): resolve()
re-derives one record from its original *raw* source file for point-in-time
debugging; ShardedDataset is for bulk, indexed iteration over the already-
*parsed* corpus (e.g. a PyTorch Dataset).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO

from pydantic import BaseModel

from awesome_log_data.base import ParsedRecord

INDEX_FILENAME = "shard_index.jsonl"
_SHARD_DIGITS = 5


class ShardIndexEntry(BaseModel):
    shard_id: int
    offset: int
    source_id: str


class ShardedDataset:
    def __init__(self, out_dir: Path, shard_size: int = 10_000) -> None:
        self.out_dir = out_dir
        self.shard_size = shard_size
        self._index: list[ShardIndexEntry] = self._load_index()
        self._file: BinaryIO | None = None
        if self._index:
            self._shard_id = self._index[-1].shard_id
            self._count_in_shard = sum(
                1 for e in self._index if e.shard_id == self._shard_id
            )
        else:
            self._shard_id = -1
            self._count_in_shard = 0

    def _index_path(self) -> Path:
        return self.out_dir / INDEX_FILENAME

    def _load_index(self) -> list[ShardIndexEntry]:
        path = self._index_path()
        if not path.exists():
            return []
        entries: list[ShardIndexEntry] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                entries.append(ShardIndexEntry.model_validate_json(stripped))
        return entries

    def _shard_path(self, shard_id: int) -> Path:
        return self.out_dir / f"{shard_id:0{_SHARD_DIGITS}d}.jsonl"

    # --- writing ---

    def append(self, source_id: str, record_ref: int | str, parsed: ParsedRecord) -> None:
        if self._shard_id == -1 or self._count_in_shard >= self.shard_size:
            self._advance_shard()
        if self._file is None:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            self._file = open(self._shard_path(self._shard_id), "ab")

        offset = self._file.tell()
        wrapped: dict[str, Any] = {
            "metadata": source_id,
            "record_ref": record_ref,
            "parsed": parsed,
        }
        self._file.write(json.dumps(wrapped).encode("utf-8") + b"\n")
        self._index.append(
            ShardIndexEntry(shard_id=self._shard_id, offset=offset, source_id=source_id)
        )
        self._count_in_shard += 1

    def _advance_shard(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        self._shard_id += 1
        self._count_in_shard = 0

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        self._write_index()

    def _write_index(self) -> None:
        with open(self._index_path(), "w", encoding="utf-8") as f:
            for entry in self._index:
                f.write(entry.model_dump_json() + "\n")

    def __enter__(self) -> ShardedDataset:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- reading ---

    def __len__(self) -> int:
        return len(self._index)

    def __getitem__(self, i: int) -> dict[str, Any]:
        entry = self._index[i]
        with open(self._shard_path(entry.shard_id), "rb") as f:
            f.seek(entry.offset)
            record: dict[str, Any] = json.loads(f.readline())
            return record

    def indices_for_source(self, source_id: str) -> list[int]:
        return [i for i, entry in enumerate(self._index) if entry.source_id == source_id]
