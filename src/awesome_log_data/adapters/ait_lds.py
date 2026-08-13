"""AIT Log Data Set (AIT-LDS v2) adapter.

Raw input is one or more per-scenario `_no-pcaps` zips (fox, harrison,
russellmitchell, shaw, wardbeck, wheeler, wilson), each containing
gather/<host_name>/logs/<...>. Scoped down from the full AIT-LDS format
list to just the formats that are genuinely structured — multiple
independently-varying fields, not a timestamp/host/program prefix wrapped
around one free-text message blob:

- apache2/*access*.log* and horde/horde-access.log — Apache combined
  format (clientip, verb, request, response, bytes, referrer, agent...).
- audit/audit.log — auditd key=value (AuditdParser).
- suricata/eve.json — structured NIDS JSON.
- monitoring/logs/logstash/<host>/*.log — Metricbeat/ECS JSON, excluding
  system.service.log specifically (same format, but ~one record per
  systemd unit per ~45s poll, mostly unchanged state, low information
  density).

Explicitly out of scope (confirmed against real samples, not just
assumed): the whole syslog family (syslog, kern.log, auth.log,
mail.log/info/warn, messages, user.log), dnsmasq.log, openvpn.log,
apache2/horde error logs, exim4/mainlog, shorewall-init.log, Logstash's
own service log (monitoring/logs/logstash/*.log with no per-host
subdirectory), redis-server.log, journal/*.journal, and the labels/,
processing/, rules/, environment/ directories (tooling/ground-truth, not
logs) — all either free-text-dominated or not logs at all.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from awesome_log_data.adapters import register
from awesome_log_data.base import DatasetId, RecordParser, SourceFile
from awesome_log_data.extractor import extract_zip
from awesome_log_data.parsers.auditd_parser import AuditdParser
from awesome_log_data.parsers.grok_parser import GrokParser
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser


def _classify(
    rel_parts: tuple[str, ...],
    apache_parser: RecordParser,
    audit_parser: RecordParser,
    json_parser: RecordParser,
) -> RecordParser | None:
    if len(rel_parts) < 4 or rel_parts[0] != "gather" or rel_parts[2] != "logs":
        return None
    category = rel_parts[3]
    name = rel_parts[-1]
    if category == "apache2" and "access" in name:
        return apache_parser
    if category == "horde" and name == "horde-access.log":
        return apache_parser
    if category == "audit" and name == "audit.log":
        return audit_parser
    if category == "suricata" and name == "eve.json":
        return json_parser
    if category == "logstash" and len(rel_parts) == 6 and "system.service" not in name:
        return json_parser
    return None


@register
class AitLdsAdapter:
    dataset_id: ClassVar[DatasetId] = "ait_lds"
    source_url: ClassVar[str] = "https://zenodo.org/records/19483937"
    license: ClassVar[str] = "CC-BY-NC-SA-4.0"

    @staticmethod
    def discover(root: Path) -> Iterator[SourceFile]:
        apache_parser: RecordParser = GrokParser("%{COMBINEDAPACHELOG}")
        audit_parser: RecordParser = AuditdParser()
        json_parser: RecordParser = JsonLinesParser()

        for zip_path in sorted(root.rglob("*.zip")):
            extracted_dir = zip_path.with_suffix("")
            extracted_files = extract_zip(zip_path, extracted_dir)
            for file_path in sorted(extracted_files):
                rel_parts = file_path.relative_to(extracted_dir).parts
                parser = _classify(rel_parts, apache_parser, audit_parser, json_parser)
                if parser is None:
                    continue
                yield SourceFile(
                    file_name=file_path.relative_to(root).as_posix(),
                    path=file_path,
                    parser=parser,
                    source_url=AitLdsAdapter.source_url,
                    license=AitLdsAdapter.license,
                    labeled=False,
                )
