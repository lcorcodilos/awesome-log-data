"""OTRF Security Datasets (Mordor) adapter.

Raw files are zips scattered under category subdirectories (e.g.
datasets/atomic/cloud/aws/host/*.zip). The full checkout (not just the
small sample this adapter was originally verified against) contains
several distinct shapes, confirmed by inspecting every zip's real
members (excluding macOS' own __MACOSX/._* AppleDouble junk, which some
zips carry alongside real content and which is not a second data file):

- **One real .json file** (133 of 206 zips) — the common case. NDJSON,
  e.g. ec2_proxy_s3_exfiltration.zip -> ...2020-09-14011940.json.
  JsonLinesParser.
- **One .log file matching the auditd prefix pattern** (2 zips, under
  datasets/atomic/linux/) — raw auditd output, same format
  AuditdParser already handles for AIT-LDS.
- **Multiple .log files that are actually JSON-lines despite the
  extension** (8 zips, datasets/compound/apt29/*/zeek/*-zeek_logs.zip)
  — Zeek's own JSON output mode (conn/dns/http/... streams), confirmed
  real, rich, multi-field records. Each qualifying file within the zip
  is yielded as its own JsonLinesParser source.
- Everything else (56 zips of pure .cap/.pcapng/.pcap ± .sha1sum
  network captures, 1 lone CSV, and 7 datasets/compound/LSASS_campaign_*
  zeek_logs.zip that are genuine Zeek TSV output, `#separator \\x09`
  headers — a format not yet supported) — no SourceFile is yielded for
  these; the zip contributes nothing rather than raising, since none of
  it matches a format this project parses. These pure-capture zips are
  also, confirmed for real, password-encrypted (OTRF's convention for
  shipping pcaps/malware samples without tripping AV scanners) — so
  discover() peeks at each zip's member names via zipfile.namelist()
  before extracting, and skips extraction entirely for zips with no
  .json/.log member. Actually extracting one would raise (wrong
  password) for no benefit, since we'd just discard the result anyway.

A zip with more than one real .json file has no observed real-world
case (checked above) and would indicate a genuinely new, unanticipated
layout, so that case still raises rather than silently guessing which
file is the "real" one.

discover() extracts each zip into a sibling directory (named after the
zip, extension stripped) and yields sources keyed by their path
relative to root so files with the same basename in different
categories don't collide in the manifest.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from awesome_log_data.adapters import register
from awesome_log_data.base import DatasetId, RecordParser, SourceFile
from awesome_log_data.extractor import extract_zip
from awesome_log_data.parsers.auditd_parser import AuditdParser, looks_like_auditd
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser, is_json_lines


def _is_macosx_junk_name(name: str) -> bool:
    return "__MACOSX" in name.split("/") or name.rsplit("/", 1)[-1].startswith("._")


def _has_candidate_member(zip_path: Path) -> bool:
    with zipfile.ZipFile(zip_path) as zf:
        return any(
            not _is_macosx_junk_name(name) and (name.endswith(".json") or name.endswith(".log"))
            for name in zf.namelist()
        )


def _classify_log_file(path: Path) -> RecordParser | None:
    if is_json_lines(path):
        return JsonLinesParser()
    if looks_like_auditd(path):
        return AuditdParser()
    return None


@register
class OtrfAdapter:
    dataset_id: ClassVar[DatasetId] = "otrf"
    source_url: ClassVar[str] = "https://github.com/OTRF/Security-Datasets"
    license: ClassVar[str] = "GPL-3.0"

    @staticmethod
    def discover(root: Path) -> Iterator[SourceFile]:
        for zip_path in sorted(root.rglob("*.zip")):
            if not _has_candidate_member(zip_path):
                continue

            extracted = extract_zip(zip_path)
            real_files = [p for p in extracted if not _is_macosx_junk_name(p.name)]
            json_files = [p for p in real_files if p.suffix == ".json"]

            if len(json_files) > 1:
                raise ValueError(
                    f"expected at most one .json file in {zip_path}, found {len(json_files)}"
                )

            if len(json_files) == 1:
                yield SourceFile(
                    file_name=json_files[0].relative_to(root).as_posix(),
                    path=json_files[0],
                    parser=JsonLinesParser(),
                    source_url=OtrfAdapter.source_url,
                    license=OtrfAdapter.license,
                    labeled=True,
                )
                continue

            log_files = sorted(p for p in real_files if p.suffix == ".log")
            for log_path in log_files:
                parser = _classify_log_file(log_path)
                if parser is None:
                    continue
                yield SourceFile(
                    file_name=log_path.relative_to(root).as_posix(),
                    path=log_path,
                    parser=parser,
                    source_url=OtrfAdapter.source_url,
                    license=OtrfAdapter.license,
                    labeled=True,
                )
