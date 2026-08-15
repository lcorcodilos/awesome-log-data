"""Parser for raw Linux auditd logs (audit.log) using the byte_offset
record reference scheme.

Every line shares the fixed prefix `type=<TYPE> msg=audit(<epoch>:<id>): `,
followed by a variable, type-dependent list of space-separated key=value
pairs (some values single- or double-quoted, occasionally themselves
containing a nested `msg='key=value ...'` blob for PAM-related types). The
prefix is parsed into named fields (type/epoch/audit_id) separately from
the tail so that the prefix's own "msg=audit(...)" doesn't collide with a
key literally named "msg" that may appear again in the tail.

The timestamp inside audit(...) is captured as a greedy, otherwise-unvalidated
group rather than a strict `\\d+\\.\\d+` pattern: real auditd writes raw
epoch.microseconds (`audit(1722867796.638:2746)`), but Splunk's attack_data
dataset re-exports the same logs with a human-readable timestamp and an extra
space before the colon (`audit(04/16/2025 08:19:50.366:45090) :`) - both are
genuinely "auditd" content, just different export tooling, confirmed against
real samples of each.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from awesome_log_data.base import ParsedRecord, RecordRefType

_PREFIX_RE = re.compile(
    r"^type=(?P<type>\S+) msg=audit\((?P<epoch>.+):(?P<audit_id>\d+)\)\s*:\s*(?P<tail>.*)$"
)
_KV_RE = re.compile(r"""(?P<key>[\w.-]+)=(?P<value>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\S+)""")


def looks_like_auditd(path: Path) -> bool:
    """True if the first non-blank line matches the auditd prefix pattern.
    Used to content-probe files whose extension alone doesn't indicate
    their format (e.g. OTRF ships raw auditd logs under a plain .log
    name, indistinguishable by extension from other .log formats).
    """
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                return _PREFIX_RE.match(stripped) is not None
    return False


class AuditdParser:
    record_ref_type: RecordRefType = "byte_offset"

    def parse(self, path: Path) -> Iterator[tuple[int, ParsedRecord]]:
        with open(path, "rb") as f:
            offset = f.tell()
            for raw in f:
                line = raw.decode("utf-8").rstrip("\r\n")
                if line:
                    yield offset, self._match(line, path, offset)
                offset = f.tell()

    def resolve(self, path: Path, ref: int) -> ParsedRecord:
        with open(path, "rb") as f:
            f.seek(ref)
            line = f.readline().decode("utf-8").rstrip("\r\n")
            return self._match(line, path, ref)

    def _match(self, line: str, path: Path, offset: int) -> ParsedRecord:
        prefix_match = _PREFIX_RE.match(line)
        if prefix_match is None:
            raise ValueError(
                f"line at byte offset {offset} in {path} did not match "
                "auditd prefix pattern 'type=... msg=audit(...): ...'"
            )
        record: ParsedRecord = {
            "type": prefix_match["type"],
            "epoch": prefix_match["epoch"],
            "audit_id": prefix_match["audit_id"],
        }
        for kv_match in _KV_RE.finditer(prefix_match["tail"]):
            value = kv_match["value"]
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            record[kv_match["key"]] = value
        return record
