"""Grok-based parser for line-oriented text logs (Apache/syslog/auth-style)
using the byte_offset record reference scheme.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pygrok import Grok

from awesome_log_data.base import ParsedRecord, RecordRefType


class GrokParser:
    record_ref_type: RecordRefType = "byte_offset"

    def __init__(self, pattern: str, encoding: str = "utf-8") -> None:
        self._grok = Grok(pattern)
        self._encoding = encoding

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        with open(path, "rb") as f:
            offset = f.tell()
            for raw in f:
                line = raw.decode(self._encoding).rstrip("\r\n")
                if line:
                    yield offset, self._match(line, path, offset)
                offset = f.tell()

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        with open(path, "rb") as f:
            f.seek(ref)
            line = f.readline().decode(self._encoding).rstrip("\r\n")
            return self._match(line, path, ref)

    def _match(self, line: str, path: Path, offset: int) -> ParsedRecord:
        result: ParsedRecord | None = self._grok.match(line)
        if result is None:
            raise ValueError(
                f"line at byte offset {offset} in {path} did not match "
                f"grok pattern {self._grok.pattern!r}"
            )
        return result
