"""CSV parser using the byte_offset record reference scheme."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from awesome_log_data.base import ParsedRecord, RecordRefType
from awesome_log_data.parsers.csv_offset_iterator import _OffsetTrackingLines


class CsvParser:
    record_ref_type: RecordRefType = "byte_offset"

    def __init__(self, encoding: str = "utf-8") -> None:
        self._encoding = encoding

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        with open(path, "rb") as fh:
            lines = _OffsetTrackingLines(fh, self._encoding)
            reader = csv.reader(lines)
            fieldnames = next(reader)
            offset = lines.tell()
            for row in reader:
                yield offset, dict(zip(fieldnames, row, strict=True))
                offset = lines.tell()

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        with open(path, "rb") as fh:
            fieldnames = next(csv.reader(_OffsetTrackingLines(fh, self._encoding)))
            fh.seek(ref)
            row = next(csv.reader(_OffsetTrackingLines(fh, self._encoding)))
            return dict(zip(fieldnames, row, strict=True))
