"""Parser for Windows Event XML dumps (one or more `<Event ...>...</Event>`
fragments concatenated in a single file, as exported by Splunk's attack_data
repo for XmlWinEventLog/sysmon:linux sourcetypes) using the byte_offset
record reference scheme.

Records are split on `</Event>` boundaries via regex, not on newlines:
embedded fields (e.g. Privileges lists) can contain real newlines, so
naive line-splitting would break individual events apart. Like EvtxParser,
resolve() re-scans the file rather than seeking+parsing a fixed-size chunk,
since events vary in byte length - no faster than parse() itself, but that
cost is only paid for a single targeted lookup, not the common bulk-read path.

Two corpus-specific corruptions are repaired/isolated before parsing:

- Some CommandLine/ScriptBlock fields contain literal, unescaped `&`
  (e.g. `&($ShellId[1]...`, `2>&1`) from the source export not XML-escaping
  process command lines. These are rewritten to `&amp;` unless already part
  of a valid entity reference.
- Some source lines are truncated mid-attribute with no closing `</Event>`
  at all. A single non-greedy regex across the whole file would match from
  that truncated tag through to the *next* record's `</Event>`, corrupting
  both. Event boundaries are instead found by pairing each `<Event` start
  with the next `</Event>` that appears before the following `<Event`
  start; a start with no such close is an unrecoverable truncated record
  and is skipped on its own, leaving the following record intact.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from xml.parsers.expat import ExpatError

import logfire
import xmltodict

from awesome_log_data.base import ParsedRecord, RecordRefType

_EVENT_START_RE = re.compile(rb"<Event[ >]")
_EVENT_END_RE = re.compile(rb"</Event>")
_BARE_AMP_RE = re.compile(rb"&(?!(?:amp|lt|gt|quot|apos|#[0-9]+|#x[0-9a-fA-F]+);)")


def _iter_event_spans(data: bytes) -> Iterator[tuple[int, bytes | None]]:
    """Yield (start_offset, raw_bytes) for each `<Event>...</Event>` fragment.

    raw_bytes is None when no closing `</Event>` was found before the next
    `<Event` start (or EOF) - a truncated record with no data to recover.
    """
    starts = [m.start() for m in _EVENT_START_RE.finditer(data)]
    for i, start in enumerate(starts):
        window_end = starts[i + 1] if i + 1 < len(starts) else len(data)
        end_match = _EVENT_END_RE.search(data, start, window_end)
        yield start, data[start:end_match.end()] if end_match else None


class XmlEventParser:
    record_ref_type: RecordRefType = "byte_offset"

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        data = path.read_bytes()
        for start, raw in _iter_event_spans(data):
            if raw is None:
                logfire.warn(
                    f"Skipping truncated record (no closing </Event>) in {str(path)} "
                    f"at byte offset {start}"
                )
                continue
            try:
                record: ParsedRecord = xmltodict.parse(
                    _BARE_AMP_RE.sub(b"&amp;", raw), attr_prefix=""
                )
                yield start, record
            except ExpatError as e:
                logfire.warn(f"Skipping record in {str(path)} with this error:\n{str(e)}")

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        data = path.read_bytes()
        for start, raw in _iter_event_spans(data):
            if start == ref and raw is not None:
                return xmltodict.parse(_BARE_AMP_RE.sub(b"&amp;", raw), attr_prefix="")
        raise LookupError(f"byte offset {ref} not found in {path}")
