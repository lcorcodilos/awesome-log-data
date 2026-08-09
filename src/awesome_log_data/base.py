"""Shared protocols and type aliases for the ingestion pipeline."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

ParsedRecord = dict[str, Any]
RecordRefType = Literal["byte_offset", "event_record_id", "array_index"]


@runtime_checkable
class RecordParser(Protocol):
    record_ref_type: RecordRefType

    def parse(self, path: Path) -> Iterator[tuple[int | str, ParsedRecord]]:
        """Stream all records in the file as (record_ref, parsed) pairs."""
        ...

    def resolve(self, path: Path, ref: int | str) -> ParsedRecord:
        """Fetch exactly one record given a record_ref previously yielded
        by parse() on this same file. Implementation is specific to the
        reference type."""
        ...
