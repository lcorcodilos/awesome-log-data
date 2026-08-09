"""JSON-array-wrapped parser (CloudTrail bulk delivery, AIT label files)
using the array_index record reference scheme.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from awesome_log_data.base import ParsedRecord, RecordRefType


class JsonArrayParser:
    record_ref_type: RecordRefType = "array_index"

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        with open(path, encoding="utf-8") as f:
            records: list[ParsedRecord] = json.load(f)["Records"]
        yield from enumerate(records)

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        with open(path, encoding="utf-8") as f:
            records: list[ParsedRecord] = json.load(f)["Records"]
        return records[ref]
