"""Shared protocols and type aliases for the ingestion pipeline."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

ParsedRecord = dict[str, Any]
RecordRefType = Literal["byte_offset", "event_record_id", "array_index"]
DatasetId = str


@runtime_checkable
class RecordParser(Protocol):
    record_ref_type: RecordRefType

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        """Stream all records in the file as (record_ref, parsed) pairs."""
        ...

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        """Fetch exactly one record given a record_ref previously yielded
        by parse() on this same file. Implementation is specific to the
        reference type."""
        ...


@dataclass(frozen=True)
class SourceFile:
    "One raw source file discovered by a DatasetAdapter, ready to parse."

    file_name: str
    path: Path
    parser: RecordParser
    source_url: str
    license: str
    labeled: bool


@runtime_checkable
class DatasetAdapter(Protocol):
    dataset_id: DatasetId

    def discover(self, root: Path) -> Iterator[SourceFile]:
        "Walk a dataset's raw files and yield one SourceFile per parseable source"
        ...


_REGISTRY: dict[DatasetId, DatasetAdapter] = {}


def register(adapter: DatasetAdapter) -> None:
    if adapter.dataset_id in _REGISTRY:
        raise ValueError(f"dataset_id {adapter.dataset_id!r} is already registered")
    _REGISTRY[adapter.dataset_id] = adapter


def get_adapter(dataset_id: DatasetId) -> DatasetAdapter:
    try:
        return _REGISTRY[dataset_id]
    except KeyError:
        raise LookupError(f"no adapter registered for dataset_id {dataset_id!r}") from None
