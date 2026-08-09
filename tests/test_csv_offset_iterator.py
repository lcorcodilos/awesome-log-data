"""Tests for CSV byte-offset tracking, including the embedded-newline-inside-
a-quoted-field case that motivates a dedicated line-decoding iterator instead
of naive per-physical-line offset tracking.
"""

from __future__ import annotations

from pathlib import Path

from awesome_log_data.parsers.csv_offset_iterator import _OffsetTrackingLines
from awesome_log_data.parsers.csv_parser import CsvParser


def test_offset_tracking_lines_decodes_and_tracks_tell(tmp_path: Path) -> None:
    path = tmp_path / "raw.txt"
    path.write_bytes(b"line one\nline two\n")

    with open(path, "rb") as fh:
        lines = _OffsetTrackingLines(fh)
        assert lines.tell() == 0
        assert next(lines) == "line one\n"
        assert lines.tell() == len(b"line one\n")
        assert next(lines) == "line two\n"
        assert lines.tell() == len(b"line one\nline two\n")


def test_offset_tracking_lines_stops_at_eof(tmp_path: Path) -> None:
    path = tmp_path / "raw.txt"
    path.write_bytes(b"only line\n")

    with open(path, "rb") as fh:
        lines = _OffsetTrackingLines(fh)
        next(lines)
        raised = False
        try:
            next(lines)
        except StopIteration:
            raised = True
        assert raised


def test_csv_parser_parse_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "simple.csv"
    path.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")

    parser = CsvParser()
    results = list(parser.parse(path))

    assert [row for _, row in results] == [
        {"id": "1", "name": "alice"},
        {"id": "2", "name": "bob"},
    ]
    assert parser.record_ref_type == "byte_offset"


def test_csv_parser_resolve_returns_record_at_ref(tmp_path: Path) -> None:
    path = tmp_path / "simple.csv"
    path.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")

    parser = CsvParser()
    refs = list(parser.parse(path))

    for ref, expected in refs:
        assert parser.resolve(path, ref) == expected


def test_csv_parser_handles_embedded_newline_in_quoted_field(tmp_path: Path) -> None:
    path = tmp_path / "embedded_newline.csv"
    path.write_bytes(
        b"id,date,detail\n"
        b'1,2020-01-01,"line one\nline two"\n'
        b"2,2020-01-02,simple\n"
    )

    parser = CsvParser()
    results = list(parser.parse(path))

    assert [row for _, row in results] == [
        {"id": "1", "date": "2020-01-01", "detail": "line one\nline two"},
        {"id": "2", "date": "2020-01-02", "detail": "simple"},
    ]

    # The second record's ref must land exactly on row 2, proving the offset
    # tracker correctly accounted for the embedded newline inside row 1's
    # quoted field rather than miscounting it as a row boundary.
    second_ref, second = results[1]
    assert parser.resolve(path, second_ref) == second


def test_csv_parser_handles_crlf_line_endings(tmp_path: Path) -> None:
    path = tmp_path / "crlf.csv"
    path.write_bytes(b"id,name\r\n1,alice\r\n2,bob\r\n")

    parser = CsvParser()
    results = list(parser.parse(path))

    assert [row for _, row in results] == [
        {"id": "1", "name": "alice"},
        {"id": "2", "name": "bob"},
    ]

    for ref, expected in results:
        assert parser.resolve(path, ref) == expected
