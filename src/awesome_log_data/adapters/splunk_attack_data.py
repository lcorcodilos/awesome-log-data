"""Splunk attack_data adapter (https://github.com/splunk/attack_data).

Raw files are one YAML manifest per attack technique/scenario directory under
datasets/ (e.g. datasets/attack_techniques/T1110.003/.../*.yml), each
declaring a `datasets:` list of one or more raw sample files (repo-root-
relative `path`, plus `sourcetype`) and the ATT&CK technique IDs
(`mitre_technique`) the scenario demonstrates. TEMPLATE.yml is not a real
manifest and is skipped. A manifest-declared path not resolving to a real
file on disk is known, expected drift in the upstream repo (confirmed
against a real checkout) and is skipped rather than treated as an error.

By real file count, three format buckets dominate: XmlWinEventLog/
sysmon:linux (Windows Event XML, one or more <Event>...</Event> fragments
per file), auditd (Linux auditd kv text - including a Splunk-specific
timestamp variant, see auditd_parser.py), and a long tail of ~150 distinct
JSON-ish sourcetypes (cloud/SaaS vendors) too heterogeneous to hand-list, so
those are recognized by content-sniffing rather than a name table - the same
approach the project's own earlier log_embedder_data prototype used. A
handful of sourcetypes (vmw-syslog, MSExchange:Management) are known to be
freeform syslog/text rather than JSON despite occasionally starting with a
JSON-like character, so they're force-skipped by name rather than
content-sniffed. Freeform text and any other unrecognized format are out of
scope for now and simply don't yield a SourceFile, matching this project's
existing precedent (see otrf.py) of skipping unsupported content rather than
guessing at it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

import yaml

from awesome_log_data.adapters import register
from awesome_log_data.base import DatasetId, RecordParser, SourceFile
from awesome_log_data.parsers.auditd_parser import AuditdParser, looks_like_auditd
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser, is_json_lines
from awesome_log_data.parsers.xml_event_parser import XmlEventParser

_XML_SOURCETYPES = {"xmlwineventlog", "sysmon:linux"}
_KV_SOURCETYPES = {"auditd"}
_FORCED_SKIP_SOURCETYPES = {"vmw-syslog", "msexchange:management"}

# File extensions a manifest-declared sample path could plausibly have if its
# format turns out to be one this adapter supports (json/ndjson/kv/xml).
# Deliberately over-inclusive: this is only used to decide what to `git lfs
# pull` before real bytes exist to content-sniff - see
# iter_lfs_candidate_paths(). discover() remains the actual authority once
# real content is present.
_LFS_CANDIDATE_EXTENSIONS = (".json", ".ndjson", ".log", ".xml")


def _iter_manifest_datasets(root: Path) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Yields (manifest, dataset_entry) for every `datasets:` entry across
    every non-TEMPLATE manifest under root/datasets/, before resolving the
    entry's path against disk or classifying its format. Shared by
    discover() and iter_lfs_candidate_paths()."""
    for yml_path in sorted((root / "datasets").rglob("*.yml")):
        if yml_path.name == "TEMPLATE.yml":
            continue

        manifest: dict[str, Any] | None = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
        if not manifest:
            continue

        for entry in manifest.get("datasets") or []:
            yield manifest, entry


def iter_lfs_candidate_paths(root: Path) -> Iterator[str]:
    """Repo-root-relative paths (leading slash stripped) worth `git lfs
    pull`ing: manifest-declared sample paths whose extension could plausibly
    be a supported format. Used by scripts/fetch_datasets.sh to scope the
    LFS pull instead of fetching the full ~23GB repo."""
    seen: set[str] = set()
    for _manifest, entry in _iter_manifest_datasets(root):
        raw_path = entry.get("path")
        if not raw_path or raw_path in seen:
            continue
        if raw_path.lower().endswith(_LFS_CANDIDATE_EXTENSIONS):
            seen.add(raw_path)
            yield raw_path.lstrip("/")


def _first_nonblank_char(path: Path) -> str | None:
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                return stripped[0]
    return None


def _classify(sourcetype: str, sample_path: Path) -> RecordParser | None:
    normalized = sourcetype.strip().lower()
    if normalized in _FORCED_SKIP_SOURCETYPES:
        return None
    if normalized in _XML_SOURCETYPES:
        return XmlEventParser()
    if normalized in _KV_SOURCETYPES:
        return AuditdParser() if looks_like_auditd(sample_path) else None

    first_char = _first_nonblank_char(sample_path)
    if first_char in ("{", "["):
        return JsonLinesParser() if is_json_lines(sample_path) else None
    if first_char == "<":
        return XmlEventParser()
    if looks_like_auditd(sample_path):
        return AuditdParser()
    return None


@register
class SplunkAttackDataAdapter:
    dataset_id: ClassVar[DatasetId] = "splunk_attack_data"
    source_url: ClassVar[str] = "https://github.com/splunk/attack_data"
    license: ClassVar[str] = "Apache-2.0"

    @staticmethod
    def discover(root: Path) -> Iterator[SourceFile]:
        for manifest, entry in _iter_manifest_datasets(root):
            raw_path = entry.get("path")
            if not raw_path:
                continue

            sample_path = root / raw_path.lstrip("/")
            if not sample_path.is_file():
                continue

            parser = _classify(entry.get("sourcetype", ""), sample_path)
            if parser is None:
                continue

            yield SourceFile(
                file_name=sample_path.relative_to(root).as_posix(),
                path=sample_path,
                parser=parser,
                source_url=SplunkAttackDataAdapter.source_url,
                license=SplunkAttackDataAdapter.license,
                labeled=bool(manifest.get("mitre_technique")),
            )
