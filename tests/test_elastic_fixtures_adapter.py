from __future__ import annotations

import json
from pathlib import Path

from awesome_log_data.adapters.elastic_fixtures import ElasticFixturesAdapter
from awesome_log_data.parsers.elastic_events_parser import ElasticEventsParser
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser


def _pipeline_dir(root: Path, package: str, data_stream: str) -> Path:
    d = root / "packages" / package / "data_stream" / data_stream / "_dev" / "test" / "pipeline"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_discover_includes_json_lines_log_files(tmp_path: Path) -> None:
    d = _pipeline_dir(tmp_path, "okta", "system")
    (d / "test-okta-system-events.log").write_text(
        '{"eventType": "user.session.start"}\n{"eventType": "user.session.end"}\n',
        encoding="utf-8",
    )

    sources = list(ElasticFixturesAdapter.discover(tmp_path))

    assert len(sources) == 1
    source = sources[0]
    assert source.file_name == (
        "packages/okta/data_stream/system/_dev/test/pipeline/test-okta-system-events.log"
    )
    assert isinstance(source.parser, JsonLinesParser)
    assert source.labeled is False
    records = list(source.parser.parse(source.path))
    assert [r["eventType"] for _ref, r in records] == [
        "user.session.start",
        "user.session.end",
    ]


def test_discover_excludes_expected_json_and_config(tmp_path: Path) -> None:
    d = _pipeline_dir(tmp_path, "okta", "system")
    (d / "test-okta-system-events.log").write_text('{"a": 1}\n', encoding="utf-8")
    (d / "test-okta-system-events.log-expected.json").write_text('{"a": 1}\n', encoding="utf-8")
    (d / "test-okta-system-events.log-config.yml").write_text("fields: {}\n", encoding="utf-8")

    sources = list(ElasticFixturesAdapter.discover(tmp_path))

    assert {s.file_name for s in sources} == {
        "packages/okta/data_stream/system/_dev/test/pipeline/test-okta-system-events.log"
    }


def test_discover_includes_events_wrapper_json_files(tmp_path: Path) -> None:
    d = _pipeline_dir(tmp_path, "auth0", "logs")
    (d / "test-login.json").write_text(
        json.dumps({"events": [{"json": {"log_id": "1", "type": "f"}}]}),
        encoding="utf-8",
    )

    sources = list(ElasticFixturesAdapter.discover(tmp_path))

    assert len(sources) == 1
    source = sources[0]
    assert source.file_name == "packages/auth0/data_stream/logs/_dev/test/pipeline/test-login.json"
    assert isinstance(source.parser, ElasticEventsParser)
    assert source.labeled is False
    records = list(source.parser.parse(source.path))
    assert [r for _ref, r in records] == [{"log_id": "1", "type": "f"}]


def test_discover_excludes_events_wrapper_json_files_with_no_valid_events(
    tmp_path: Path,
) -> None:
    # citrix_adc-style: every event wraps plain syslog text, not JSON.
    d = _pipeline_dir(tmp_path, "citrix_adc", "log")
    (d / "test-citrix.json").write_text(
        json.dumps({"events": [{"message": "<123> not json, just syslog text"}]}),
        encoding="utf-8",
    )

    sources = list(ElasticFixturesAdapter.discover(tmp_path))

    assert sources == []


def test_discover_excludes_expected_json_from_wrapper_json_matching_too(tmp_path: Path) -> None:
    d = _pipeline_dir(tmp_path, "auth0", "logs")
    (d / "test-login.json").write_text(
        json.dumps({"events": [{"json": {"a": 1}}]}), encoding="utf-8"
    )
    (d / "test-login.json-expected.json").write_text(
        json.dumps({"events": [{"json": {"a": 1}}]}), encoding="utf-8"
    )

    sources = list(ElasticFixturesAdapter.discover(tmp_path))

    assert {s.file_name for s in sources} == {
        "packages/auth0/data_stream/logs/_dev/test/pipeline/test-login.json"
    }


def test_discover_excludes_non_json_log_files(tmp_path: Path) -> None:
    d = _pipeline_dir(tmp_path, "bluecoat", "director")
    (d / "test-generated.log").write_text(
        "ntpd[1001]: kernel time sync enabled\nauditd[5699]: rotating log files\n",
        encoding="utf-8",
    )

    sources = list(ElasticFixturesAdapter.discover(tmp_path))

    assert sources == []


def test_discover_excludes_files_with_a_later_malformed_line(tmp_path: Path) -> None:
    # A valid first line isn't enough — some real fixtures mix bare JSON
    # with syslog-prefixed JSON, or end with a deliberately malformed line
    # used to test the real ingest pipeline's error handling.
    d = _pipeline_dir(tmp_path, "cyberarkpas", "monitor")
    (d / "test-monitor.log").write_text(
        '{"a": 1}\n2026-01-01T00:00:01 host {"a": 2}\n',
        encoding="utf-8",
    )

    sources = list(ElasticFixturesAdapter.discover(tmp_path))

    assert sources == []


def test_discover_finds_multiple_packages_without_collision(tmp_path: Path) -> None:
    okta_dir = _pipeline_dir(tmp_path, "okta", "system")
    (okta_dir / "test-events.log").write_text('{"a": 1}\n', encoding="utf-8")
    aws_dir = _pipeline_dir(tmp_path, "aws", "cloudtrail")
    (aws_dir / "test-events.log").write_text('{"b": 2}\n', encoding="utf-8")

    sources = list(ElasticFixturesAdapter.discover(tmp_path))

    assert {s.file_name for s in sources} == {
        "packages/okta/data_stream/system/_dev/test/pipeline/test-events.log",
        "packages/aws/data_stream/cloudtrail/_dev/test/pipeline/test-events.log",
    }
