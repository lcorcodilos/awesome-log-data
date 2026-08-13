"""Parser for the {"events": [...]} test-harness wrapper format used by
some elastic/integrations pipeline fixtures, using the array_index record
reference scheme.

Each element of "events" is normalized before being treated as a record:
- "@timestamp" and "ecs" keys are stripped if present (kept otherwise).
- If exactly one key remains, the wrapper is unwrapped and its value used
  directly as the record — decoding it first if it's a JSON-encoded string
  (the common shape: {"message": "{...}"}), so the actual structured
  content is what ends up in the record, not an opaque string.
- An event that normalizes to something other than a non-empty dict (e.g.
  nothing left after stripping, or a single remaining value that isn't
  JSON — confirmed real case: citrix_adc wraps plain syslog text in
  "message") is skipped, not raised on — array_index stays a dense,
  gap-free sequence over just the events that qualified, computed
  identically by parse() and resolve() on every call.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from awesome_log_data.base import ParsedRecord, RecordRefType

_STRIPPED_KEYS = {"@timestamp", "ecs"}


def normalize_event(event: object) -> ParsedRecord | None:
    if not isinstance(event, dict):
        return None
    stripped = {k: v for k, v in event.items() if k not in _STRIPPED_KEYS}
    if len(stripped) != 1:
        return stripped if stripped else None
    value = next(iter(stripped.values()))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _normalized_events(path: Path) -> Iterator[ParsedRecord]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for event in data["events"]:
        record = normalize_event(event)
        if record is not None:
            yield record


class ElasticEventsParser:
    record_ref_type: RecordRefType = "array_index"

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        yield from enumerate(_normalized_events(path))

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        for index, record in enumerate(_normalized_events(path)):
            if index == ref:
                return record
        raise LookupError(f"array_index {ref} not found in {path}")
