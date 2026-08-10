"""Shared protocols and type aliases for the ingestion pipeline."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

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
    """Adapters are never instantiated — the class itself is the singleton,
    matched structurally against this protocol at the class level (see
    register())."""

    dataset_id: ClassVar[DatasetId]

    @staticmethod
    def discover(root: Path) -> Iterator[SourceFile]:
        "Walk a dataset's raw files and yield one SourceFile per parseable source"
        ...
