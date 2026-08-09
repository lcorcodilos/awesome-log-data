from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from awesome_log_data.parsers.json_array_parser import JsonArrayParser


def _write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps({"Records": records}), encoding="utf-8")


def test_parse_yields_records_by_array_index(tmp_path: Path) -> None:
    records = [{"eventName": "A"}, {"eventName": "B"}, {"eventName": "C"}]
    path = tmp_path / "records.json"
    _write_records(path, records)

    parser = JsonArrayParser()
    results = list(parser.parse(path))

    assert results == [(0, records[0]), (1, records[1]), (2, records[2])]
    assert parser.record_ref_type == "array_index"


def test_resolve_returns_record_at_index(tmp_path: Path) -> None:
    records = [{"eventName": "A"}, {"eventName": "B"}, {"eventName": "C"}]
    path = tmp_path / "records.json"
    _write_records(path, records)

    parser = JsonArrayParser()
    for i, expected in enumerate(records):
        assert parser.resolve(path, i) == expected
