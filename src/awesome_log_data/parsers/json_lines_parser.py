"""JSON Lines parser using the byte_offset record reference scheme."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from awesome_log_data.base import ParsedRecord, RecordRefType


def is_json_lines(path: Path) -> bool:
    """True if every non-blank line in path is valid standalone JSON, and at
    least one such line exists. Used to content-probe files whose extension
    doesn't reliably indicate their format (e.g. some OTRF/Elastic fixtures
    ship JSON-lines under a .log name).

    Checking every line (not just the first) matters: some real fixture
    files mix bare JSON lines with syslog-prefixed JSON (a hybrid format,
    not real NDJSON — confirmed in Elastic's cyberarkpas fixture), and some
    end with a deliberately malformed line used to test a real ingest
    pipeline's error handling (confirmed in Elastic's azure_frontdoor
    fixture) — neither is safe to treat as uniformly parseable from just
    the first line.
    """
    saw_any_line = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            saw_any_line = True
            try:
                json.loads(stripped)
            except json.JSONDecodeError:
                return False
    return saw_any_line


class JsonLinesParser:
    record_ref_type: RecordRefType = "byte_offset"

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        with open(path, "rb") as f:
            offset = f.tell()
            for raw in f:
                if raw.strip():
                    record: ParsedRecord = json.loads(raw)
                    yield offset, record
                offset = f.tell()

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        with open(path, "rb") as f:
            f.seek(ref)
            record: ParsedRecord = json.loads(f.readline())
            return record
