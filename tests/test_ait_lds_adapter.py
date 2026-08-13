from __future__ import annotations

import zipfile
from pathlib import Path

from awesome_log_data.adapters.ait_lds import AitLdsAdapter
from awesome_log_data.parsers.auditd_parser import AuditdParser
from awesome_log_data.parsers.grok_parser import GrokParser
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser

_APACHE_LINE = (
    '172.17.130.196 - - [19/Jan/2022:07:46:29 +0000] "GET / HTTP/1.1" 200 6128 "-" "-"\n'
)
_AUDIT_LINE = "type=LOGIN msg=audit(1642205341.341:359): pid=4733 uid=0 res=1\n"
_JSON_LINE = '{"eventName": "A"}\n'
_SYSLOG_LINE = "Jan 19 06:32:56 webserver systemd[1]: Starting daily cleanup\n"

_MEMBERS = {
    # included
    "gather/webserver/logs/apache2/access.log": _APACHE_LINE,
    "gather/webserver/logs/apache2/other_vhosts_access.log.2": _APACHE_LINE,
    "gather/webserver/logs/horde/horde-access.log": _APACHE_LINE,
    "gather/webserver/logs/audit/audit.log": _AUDIT_LINE,
    "gather/webserver/logs/suricata/eve.json": _JSON_LINE,
    "gather/monitoring/logs/logstash/internal-share/2022-01-14-system.cpu.log": _JSON_LINE,
    # excluded
    "gather/webserver/logs/apache2/error.log": "[Wed Jan 19 06:25:06 2022] [core:notice] msg\n",
    "gather/webserver/logs/horde/horde-error.log": "[Sun Jan 16 08:18:19 2022] [:error] msg\n",
    "gather/webserver/logs/syslog": _SYSLOG_LINE,
    "gather/webserver/logs/auth.log": _SYSLOG_LINE,
    "gather/webserver/logs/audit/audit.log.wrong": _AUDIT_LINE,
    "gather/monitoring/logs/logstash/internal-share/2022-01-14-system.service.log": _JSON_LINE,
    "gather/monitoring/logs/logstash/logstash-plain.log": "[2022-01-20T00:00:09] INFO msg\n",
    "gather/webserver/logs/journal/abc/system.journal": "binary-stub",
    "labels/webserver/logs/audit/audit.log": _AUDIT_LINE,
}


def _make_zip(zip_path: Path, members: dict[str, str]) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)


def test_discover_includes_only_the_four_structured_formats(tmp_path: Path) -> None:
    _make_zip(tmp_path / "fox_no-pcaps.zip", _MEMBERS)

    sources = list(AitLdsAdapter.discover(tmp_path))

    assert {s.file_name for s in sources} == {
        "fox_no-pcaps/gather/webserver/logs/apache2/access.log",
        "fox_no-pcaps/gather/webserver/logs/apache2/other_vhosts_access.log.2",
        "fox_no-pcaps/gather/webserver/logs/horde/horde-access.log",
        "fox_no-pcaps/gather/webserver/logs/audit/audit.log",
        "fox_no-pcaps/gather/webserver/logs/suricata/eve.json",
        "fox_no-pcaps/gather/monitoring/logs/logstash/internal-share/2022-01-14-system.cpu.log",
    }


def test_discover_assigns_correct_parser_per_format(tmp_path: Path) -> None:
    _make_zip(tmp_path / "fox_no-pcaps.zip", _MEMBERS)

    by_name = {s.file_name: s for s in AitLdsAdapter.discover(tmp_path)}

    apache = by_name["fox_no-pcaps/gather/webserver/logs/apache2/access.log"]
    assert isinstance(apache.parser, GrokParser)
    assert list(apache.parser.parse(apache.path))[0][1]["clientip"] == "172.17.130.196"

    horde = by_name["fox_no-pcaps/gather/webserver/logs/horde/horde-access.log"]
    assert isinstance(horde.parser, GrokParser)

    audit = by_name["fox_no-pcaps/gather/webserver/logs/audit/audit.log"]
    assert isinstance(audit.parser, AuditdParser)
    assert list(audit.parser.parse(audit.path))[0][1]["type"] == "LOGIN"

    suricata = by_name["fox_no-pcaps/gather/webserver/logs/suricata/eve.json"]
    assert isinstance(suricata.parser, JsonLinesParser)

    metric = by_name[
        "fox_no-pcaps/gather/monitoring/logs/logstash/internal-share/2022-01-14-system.cpu.log"
    ]
    assert isinstance(metric.parser, JsonLinesParser)


def test_discover_marks_sources_unlabeled(tmp_path: Path) -> None:
    _make_zip(tmp_path / "fox_no-pcaps.zip", _MEMBERS)

    sources = list(AitLdsAdapter.discover(tmp_path))

    assert all(s.labeled is False for s in sources)


def test_discover_finds_multiple_scenario_zips(tmp_path: Path) -> None:
    _make_zip(tmp_path / "fox_no-pcaps.zip", _MEMBERS)
    _make_zip(tmp_path / "harrison_no-pcaps.zip", _MEMBERS)

    sources = list(AitLdsAdapter.discover(tmp_path))

    scenario_prefixes = {s.file_name.split("/")[0] for s in sources}
    assert scenario_prefixes == {"fox_no-pcaps", "harrison_no-pcaps"}
