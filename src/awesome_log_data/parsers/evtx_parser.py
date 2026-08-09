"""EVTX parser using the event_record_id record reference scheme. EVTX is
binary chunk-framed, not byte-seekable, so resolve() has no faster lookup
than a linear scan — same cost as parse(). Worth documenting so a consumer
doesn't expect O(1) lookups on this reference type.

PyEvtxParser.records_json() can yield a non-dict entry (e.g. a RuntimeError
object) in place of a record if it hits an invalid chunk, rather than raising
— its own docs recommend skipping those and continuing rather than letting
one bad record abort the whole file.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from evtx import PyEvtxParser

from awesome_log_data.base import ParsedRecord, RecordRefType


class EvtxParser:
    record_ref_type: RecordRefType = "event_record_id"

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        for rec in PyEvtxParser(str(path)).records_json():
            if not isinstance(rec, dict):
                continue
            data: ParsedRecord = json.loads(rec["data"])
            yield data["Event"]["System"]["EventRecordID"], data

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        for rec in PyEvtxParser(str(path)).records_json():
            if not isinstance(rec, dict):
                continue
            data: ParsedRecord = json.loads(rec["data"])
            if data["Event"]["System"]["EventRecordID"] == ref:
                return data
        raise LookupError(f"EventRecordID {ref} not found in {path}")
