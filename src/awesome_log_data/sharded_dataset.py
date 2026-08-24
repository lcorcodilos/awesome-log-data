"""Shards parsed records as JSONL across fixed-size files within a directory,
maintaining a Parquet index (global row -> shard file + byte offset +
source_id + record_ref) for random access into a large parsed corpus without
loading it into memory. Write with append(), read with len()/[]/indices_for_source().

Shard files hold the bare parsed record on each line - no source_id/record_ref
wrapper - since they're meant to be read directly as the training corpus.
Provenance (which source file, and the ref to re-derive the record from it)
lives only in the index, one ShardIndexEntry per record.

`source_id` is interned as a small int rather than stored as a repeated
string: a source file's records are written contiguously, so the same
(often long) path string would otherwise repeat once per record. The
string<->int mapping lives in a sidecar file, source_ids.jsonl (one JSON
string per line; line number is the int id) - see the `source_ids` property.

This complements, not replaces, RecordParser.resolve() (base.py): resolve()
re-derives one record from its original *raw* source file for point-in-time
debugging; ShardedDataset is for bulk, indexed iteration over the already-
*parsed* corpus (e.g. a PyTorch Dataset).
"""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import BinaryIO

import polars as pl
from pydantic import BaseModel

from awesome_log_data.base import ParsedRecord

INDEX_FILENAME = "shard_index.parquet"
SOURCE_IDS_FILENAME = "source_ids.jsonl"
_SHARD_DIGITS = 5


class ShardIndexEntry(BaseModel):
    shard_id: int
    offset: int
    source_id: int
    record_ref: int | str


class ShardedDataset:
    def __init__(self, out_dir: Path, shard_size: int = 10_000) -> None:
        self.out_dir = out_dir
        self.shard_size = shard_size
        self._source_id_to_int: dict[str, int] = self._load_source_id_to_int()
        self._index: list[ShardIndexEntry] = self._load_index()
        self._file: BinaryIO | None = None
        if self._index:
            self._shard_id = self._index[-1].shard_id
            self._count_in_shard = sum(1 for e in self._index if e.shard_id == self._shard_id)
        else:
            self._shard_id = -1
            self._count_in_shard = 0

    def _index_path(self) -> Path:
        return self.out_dir / INDEX_FILENAME

    def _source_ids_path(self) -> Path:
        return self.out_dir / SOURCE_IDS_FILENAME

    def _load_index(self) -> list[ShardIndexEntry]:
        path = self._index_path()
        if not path.exists():
            return []
        df = pl.read_parquet(path)
        return [ShardIndexEntry.model_validate(row) for row in df.to_dicts()]

    def _load_source_id_to_int(self) -> dict[str, int]:
        path = self._source_ids_path()
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            source_ids = [json.loads(line) for line in f if line.strip()]
        return {s: i for i, s in enumerate(source_ids)}

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
        self._file.write(json.dumps(parsed).encode("utf-8") + b"\n")
        source_id_int = self._intern_source_id(source_id)
        self._index.append(
            ShardIndexEntry(
                shard_id=self._shard_id,
                offset=offset,
                source_id=source_id_int,
                record_ref=record_ref,
            )
        )
        self._count_in_shard += 1

    def _intern_source_id(self, source_id: str) -> int:
        existing = self._source_id_to_int.get(source_id)
        if existing is not None:
            return existing
        new_id = len(self._source_id_to_int)
        self._source_id_to_int[source_id] = new_id
        return new_id

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
        self._write_source_ids()

    def _write_index(self) -> None:
        pl.DataFrame(self._index).write_parquet(self._index_path(), mkdir=True)

    def _write_source_ids(self) -> None:
        with open(self._source_ids_path(), "w", encoding="utf-8") as f:
            for source_id in self._source_id_to_int:
                f.write(json.dumps(source_id) + "\n")

    def __enter__(self) -> ShardedDataset:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- reading ---

    def __len__(self) -> int:
        return len(self._index)

    def __getitem__(self, i: int) -> ParsedRecord:
        entry = self._index[i]
        with open(self._shard_path(entry.shard_id), "rb") as f:
            f.seek(entry.offset)
            record: ParsedRecord = json.loads(f.readline())
            return record

    def indices_for_source(self, source_id: str) -> list[int]:
        source_id_int = self._source_id_to_int.get(source_id)
        if source_id_int is None:
            return []
        return [i for i, entry in enumerate(self._index) if entry.source_id == source_id_int]

    @property
    def index(self) -> list[ShardIndexEntry]:
        return self._index

    @property
    def source_ids(self) -> list[str]:
        return list(self._source_id_to_int)

    @cached_property
    def index_df(self) -> pl.DataFrame:
        return pl.DataFrame(self._index)
