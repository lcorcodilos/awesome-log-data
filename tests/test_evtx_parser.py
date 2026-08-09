from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from awesome_log_data.parsers.evtx_parser import EvtxParser

FIXTURE = Path(__file__).parent / "data" / "example.evtx"


class _FakeEvtxParser:
    """Stands in for PyEvtxParser, simulating its documented behavior of
    yielding a non-dict entry in place of a record it failed to parse."""

    def __init__(self, path: str) -> None:
        self._path = path

    def records_json(self) -> list[object]:
        def record(event_record_id: int) -> dict[str, str]:
            return {"data": json.dumps({"Event": {"System": {"EventRecordID": event_record_id}}})}

        return [record(1), RuntimeError("invalid chunk"), record(2)]


def test_parse_yields_event_record_id_and_full_event() -> None:
    parser = EvtxParser()
    results = list(parser.parse(FIXTURE))

    assert len(results) == 5
    assert parser.record_ref_type == "event_record_id"
    for ref, data in results:
        assert isinstance(ref, int)
        assert data["Event"]["System"]["EventRecordID"] == ref


def test_resolve_returns_record_matching_ref() -> None:
    parser = EvtxParser()
    results = list(parser.parse(FIXTURE))

    for ref, expected in results:
        assert parser.resolve(FIXTURE, ref) == expected


def test_resolve_raises_lookup_error_for_unknown_ref() -> None:
    parser = EvtxParser()

    with pytest.raises(LookupError):
        parser.resolve(FIXTURE, -1)


def test_parse_skips_non_dict_entries_from_records_json() -> None:
    parser = EvtxParser()

    with patch("awesome_log_data.parsers.evtx_parser.PyEvtxParser", _FakeEvtxParser):
        results = list(parser.parse(Path("unused.evtx")))

    assert [ref for ref, _ in results] == [1, 2]


def test_resolve_skips_non_dict_entries_from_records_json() -> None:
    parser = EvtxParser()

    with patch("awesome_log_data.parsers.evtx_parser.PyEvtxParser", _FakeEvtxParser):
        record = parser.resolve(Path("unused.evtx"), 2)

    assert record["Event"]["System"]["EventRecordID"] == 2
