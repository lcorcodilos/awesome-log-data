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
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from xml.parsers.expat import ExpatError

import logfire
import xmltodict

from awesome_log_data.base import ParsedRecord, RecordRefType

_EVENT_RE = re.compile(rb"<Event[ >].*?</Event>", re.DOTALL)


class XmlEventParser:
    record_ref_type: RecordRefType = "byte_offset"

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        data = path.read_bytes()
        for match in _EVENT_RE.finditer(data):
            try:
                record: ParsedRecord = xmltodict.parse(match.group(), attr_prefix="")
                yield match.start(), record
            except ExpatError as e:
                logfire.warn(f"Skipping record in {str(path)} with this error:\n{str(e)}")

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        data = path.read_bytes()
        for match in _EVENT_RE.finditer(data):
            if match.start() == ref:
                record: ParsedRecord = xmltodict.parse(match.group(), attr_prefix="")
                return record
        raise LookupError(f"byte offset {ref} not found in {path}")
