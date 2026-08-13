from __future__ import annotations

import json
from pathlib import Path

import pytest

from awesome_log_data.parsers.elastic_events_parser import ElasticEventsParser


def _write_events(path: Path, events: list[object]) -> None:
    path.write_text(json.dumps({"events": events}), encoding="utf-8")


def test_parse_unwraps_single_key_event_with_json_string_value(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    _write_events(path, [{"message": json.dumps({"eventName": "A"})}])

    parser = ElasticEventsParser()
    results = list(parser.parse(path))

    assert results == [(0, {"eventName": "A"})]
    assert parser.record_ref_type == "array_index"


def test_parse_unwraps_single_key_event_with_dict_value(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    _write_events(path, [{"json": {"log_id": "1", "type": "f"}}])

    parser = ElasticEventsParser()
    results = list(parser.parse(path))

    assert results == [(0, {"log_id": "1", "type": "f"})]


def test_parse_strips_timestamp_and_ecs_but_keeps_remaining_multi_key_event(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.json"
    _write_events(
        path,
        [
            {
                "@timestamp": "2021-08-13T09:37:27.177Z",
                "ecs": {"version": "1.9.0"},
                "json": {"cb_server": "X"},
                "tags": ["forwarded"],
            }
        ],
    )

    parser = ElasticEventsParser()
    _ref, record = next(iter(parser.parse(path)))

    assert record == {"json": {"cb_server": "X"}, "tags": ["forwarded"]}


def test_parse_skips_event_that_is_only_timestamp_and_ecs(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    _write_events(
        path,
        [
            {"@timestamp": "2021-08-13T09:37:27.177Z", "ecs": {"version": "1.9.0"}},
            {"message": json.dumps({"a": 1})},
        ],
    )

    parser = ElasticEventsParser()
    results = list(parser.parse(path))

    assert [record for _ref, record in results] == [{"a": 1}]


def test_parse_skips_single_key_event_with_undecodable_string_value(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    _write_events(
        path,
        [
            {"message": "<123> not json, just a raw syslog line"},
            {"message": json.dumps({"a": 1})},
        ],
    )

    parser = ElasticEventsParser()
    results = list(parser.parse(path))

    assert [record for _ref, record in results] == [{"a": 1}]


def test_resolve_matches_parse_indices_even_with_skipped_events_interspersed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.json"
    _write_events(
        path,
        [
            {"message": json.dumps({"a": 1})},
            {"@timestamp": "x", "ecs": {}},
            {"message": json.dumps({"a": 2})},
        ],
    )

    parser = ElasticEventsParser()
    results = list(parser.parse(path))

    for ref, expected in results:
        assert parser.resolve(path, ref) == expected


def test_resolve_raises_lookup_error_for_unknown_ref(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    _write_events(path, [{"message": json.dumps({"a": 1})}])

    parser = ElasticEventsParser()

    with pytest.raises(LookupError):
        parser.resolve(path, 5)
