from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from awesome_log_data.parsers.json_lines_parser import JsonLinesParser


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def test_parse_yields_all_records_in_order(tmp_path: Path) -> None:
    records = [{"a": 1}, {"a": 2}, {"a": 3}]
    path = tmp_path / "sample.jsonl"
    _write_jsonl(path, records)

    parser = JsonLinesParser()
    results = list(parser.parse(path))

    assert [parsed for _, parsed in results] == records
    assert parser.record_ref_type == "byte_offset"


def test_resolve_returns_record_at_ref(tmp_path: Path) -> None:
    records = [{"a": 1}, {"a": 2}, {"a": 3}]
    path = tmp_path / "sample.jsonl"
    _write_jsonl(path, records)

    parser = JsonLinesParser()
    refs = list(parser.parse(path))

    for ref, expected in refs:
        assert parser.resolve(path, ref) == expected
