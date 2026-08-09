"""JSON Lines parser using the byte_offset record reference scheme."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from awesome_log_data.base import ParsedRecord, RecordRefType


class JsonLinesParser:
    record_ref_type: RecordRefType = "byte_offset"

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        with open(path, "rb") as f:
            offset = f.tell()
            for raw in f:
                record: ParsedRecord = json.loads(raw)
                yield offset, record
                offset = f.tell()

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        with open(path, "rb") as f:
            f.seek(ref)
            record: ParsedRecord = json.loads(f.readline())
            return record
