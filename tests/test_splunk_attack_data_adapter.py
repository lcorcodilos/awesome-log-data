from __future__ import annotations

import shutil
from pathlib import Path

from awesome_log_data.adapters.splunk_attack_data import (
    SplunkAttackDataAdapter,
    iter_lfs_candidate_paths,
)
from awesome_log_data.parsers.auditd_parser import AuditdParser
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser
from awesome_log_data.parsers.xml_event_parser import XmlEventParser

FIXTURES = Path(__file__).parent / "fixtures" / "splunk_attack_data"


def _write_manifest(root: Path, rel_dir: str, manifest_yaml: str, name: str = "manifest") -> Path:
    manifest_dir = root / "datasets" / rel_dir
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{name}.yml"
    manifest_path.write_text(manifest_yaml, encoding="utf-8")
    return manifest_dir


def _copy_sample(manifest_dir: Path, fixture_name: str) -> None:
    shutil.copy(FIXTURES / fixture_name, manifest_dir / fixture_name)


_FULL_MANIFEST = """\
author: Test
id: test-manifest
date: '2025-01-01'
description: Test manifest combining json/kv/xml samples
environment: attack_range
directory: T1234/test_dir
mitre_technique:
- T1234
datasets:
- name: cloudtrail
  path: /datasets/T1234/test_dir/aws_cloudtrail_events.json
  sourcetype: aws:cloudtrail
  source: aws:cloudtrail
- name: auditd
  path: /datasets/T1234/test_dir/auditd_proctitle_access_cred.log
  sourcetype: auditd
  source: auditd
- name: winevent
  path: /datasets/T1234/test_dir/windows-security.log
  sourcetype: XmlWinEventLog
  source: XmlWinEventLog:Security
"""


_ALL_FIXTURES = (
    "aws_cloudtrail_events.json",
    "auditd_proctitle_access_cred.log",
    "windows-security.log",
)


def test_discover_finds_json_kv_and_xml_samples_from_one_manifest(tmp_path: Path) -> None:
    manifest_dir = _write_manifest(tmp_path, "T1234/test_dir", _FULL_MANIFEST)
    for fixture in _ALL_FIXTURES:
        _copy_sample(manifest_dir, fixture)

    sources = {s.file_name: s for s in SplunkAttackDataAdapter.discover(tmp_path)}

    assert len(sources) == 3
    json_source = sources["datasets/T1234/test_dir/aws_cloudtrail_events.json"]
    assert isinstance(json_source.parser, JsonLinesParser)
    assert json_source.labeled is True
    assert json_source.license == "Apache-2.0"
    assert json_source.source_url == "https://github.com/splunk/attack_data"

    kv_source = sources["datasets/T1234/test_dir/auditd_proctitle_access_cred.log"]
    assert isinstance(kv_source.parser, AuditdParser)

    xml_source = sources["datasets/T1234/test_dir/windows-security.log"]
    assert isinstance(xml_source.parser, XmlEventParser)


def test_discover_parses_real_records_from_each_format(tmp_path: Path) -> None:
    manifest_dir = _write_manifest(tmp_path, "T1234/test_dir", _FULL_MANIFEST)
    for fixture in _ALL_FIXTURES:
        _copy_sample(manifest_dir, fixture)

    sources = {s.file_name: s for s in SplunkAttackDataAdapter.discover(tmp_path)}

    json_records = list(
        sources["datasets/T1234/test_dir/aws_cloudtrail_events.json"].parser.parse(
            sources["datasets/T1234/test_dir/aws_cloudtrail_events.json"].path
        )
    )
    assert len(json_records) == 2
    assert json_records[0][1]["eventName"] == "UpdateFunctionCode20150331v2"

    kv_records = list(
        sources["datasets/T1234/test_dir/auditd_proctitle_access_cred.log"].parser.parse(
            sources["datasets/T1234/test_dir/auditd_proctitle_access_cred.log"].path
        )
    )
    assert len(kv_records) == 91
    assert kv_records[0][1]["type"] == "PROCTITLE"

    xml_records = list(
        sources["datasets/T1234/test_dir/windows-security.log"].parser.parse(
            sources["datasets/T1234/test_dir/windows-security.log"].path
        )
    )
    assert len(xml_records) == 2
    assert xml_records[0][1]["Event"]["System"]["EventID"] == "4688"


def test_discover_skips_template_yml(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "T1234/test_dir", _FULL_MANIFEST, name="TEMPLATE")

    sources = list(SplunkAttackDataAdapter.discover(tmp_path))

    assert sources == []


def test_discover_skips_manifest_entries_whose_path_does_not_resolve(tmp_path: Path) -> None:
    # The real attack_data repo has known drift where ~10% of manifest-declared
    # paths don't resolve to a real file on disk - this must be a silent skip,
    # not an error.
    _write_manifest(tmp_path, "T1234/test_dir", _FULL_MANIFEST)
    # Deliberately don't copy any of the sample files.

    sources = list(SplunkAttackDataAdapter.discover(tmp_path))

    assert sources == []


def test_discover_sets_labeled_false_when_manifest_has_no_mitre_technique(tmp_path: Path) -> None:
    manifest = """\
author: Test
id: no-technique
date: '2025-01-01'
description: no mitre_technique field
environment: attack_range
directory: T9999/test_dir
datasets:
- name: cloudtrail
  path: /datasets/T9999/test_dir/aws_cloudtrail_events.json
  sourcetype: aws:cloudtrail
  source: aws:cloudtrail
"""
    manifest_dir = _write_manifest(tmp_path, "T9999/test_dir", manifest)
    _copy_sample(manifest_dir, "aws_cloudtrail_events.json")

    (source,) = list(SplunkAttackDataAdapter.discover(tmp_path))

    assert source.labeled is False


def test_discover_skips_forced_text_sourcetypes(tmp_path: Path) -> None:
    manifest = """\
author: Test
id: forced-text
date: '2025-01-01'
description: vmw-syslog is explicitly out of scope for v1
environment: attack_range
directory: T8888/test_dir
mitre_technique:
- T8888
datasets:
- name: syslog
  path: /datasets/T8888/test_dir/vmware.log
  sourcetype: vmw-syslog
  source: vmw-syslog
"""
    manifest_dir = _write_manifest(tmp_path, "T8888/test_dir", manifest)
    (manifest_dir / "vmware.log").write_text(
        '{"this": "looks like json but should still be skipped"}\n', encoding="utf-8"
    )

    sources = list(SplunkAttackDataAdapter.discover(tmp_path))

    assert sources == []


def test_discover_classifies_long_tail_json_sourcetype_by_content_sniff(tmp_path: Path) -> None:
    # Most of the real dataset's JSON-ish sourcetypes (o365, azure, okta,
    # crowdstrike, ...) aren't individually hardcoded - they're recognized by
    # sniffing the first line, matching log_embedder_data's own approach.
    manifest = """\
author: Test
id: long-tail
date: '2025-01-01'
description: an unhardcoded sourcetype that is still real ndjson
environment: attack_range
directory: T7777/test_dir
mitre_technique:
- T7777
datasets:
- name: some_saas_product
  path: /datasets/T7777/test_dir/events.log
  sourcetype: some:unhardcoded:saas:sourcetype
  source: some:unhardcoded:saas:sourcetype
"""
    manifest_dir = _write_manifest(tmp_path, "T7777/test_dir", manifest)
    (manifest_dir / "events.log").write_text('{"eventName": "Login"}\n', encoding="utf-8")

    (source,) = list(SplunkAttackDataAdapter.discover(tmp_path))

    assert isinstance(source.parser, JsonLinesParser)


def test_iter_lfs_candidate_paths_filters_by_extension_and_strips_leading_slash(
    tmp_path: Path,
) -> None:
    manifest = """\
author: Test
id: mixed-extensions
date: '2025-01-01'
description: mix of candidate and non-candidate extensions
environment: attack_range
directory: T6666/test_dir
mitre_technique:
- T6666
datasets:
- name: a
  path: /datasets/T6666/test_dir/a.json
  sourcetype: aws:cloudtrail
  source: aws:cloudtrail
- name: b
  path: /datasets/T6666/test_dir/b.xml
  sourcetype: XmlWinEventLog
  source: XmlWinEventLog:Security
- name: c
  path: /datasets/T6666/test_dir/c.pcap
  sourcetype: pcap
  source: pcap
"""
    _write_manifest(tmp_path, "T6666/test_dir", manifest)
    # No need to actually create the sample files - this only reads manifests.

    paths = list(iter_lfs_candidate_paths(tmp_path))

    assert paths == ["datasets/T6666/test_dir/a.json", "datasets/T6666/test_dir/b.xml"]


def test_iter_lfs_candidate_paths_skips_template_yml(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "T6666/test_dir", _FULL_MANIFEST, name="TEMPLATE")

    assert list(iter_lfs_candidate_paths(tmp_path)) == []
