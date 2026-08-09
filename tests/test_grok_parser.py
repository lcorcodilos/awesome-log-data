from __future__ import annotations

from pathlib import Path

import pytest

from awesome_log_data.parsers.grok_parser import GrokParser

FIXTURE = Path(__file__).parent / "data" / "apache.log"


def test_parse_matches_combined_apache_log_format() -> None:
    parser = GrokParser("%{COMBINEDAPACHELOG}")
    results = list(parser.parse(FIXTURE))

    with open(FIXTURE, encoding="utf-8") as f:
        expected_count = sum(1 for line in f if line.strip())
    assert len(results) == expected_count
    assert parser.record_ref_type == "byte_offset"

    _, first = results[0]
    assert first["clientip"] == "172.17.130.196"
    assert first["verb"] == "GET"
    assert first["response"] == "200"


def test_resolve_returns_record_at_ref() -> None:
    parser = GrokParser("%{COMBINEDAPACHELOG}")
    results = list(parser.parse(FIXTURE))

    # Sampling is enough exercise for resolve(); the full fixture is ~1900 lines.
    for ref, expected in results[:20]:
        assert parser.resolve(FIXTURE, ref) == expected


def test_parse_raises_on_unmatched_line(tmp_path: Path) -> None:
    path = tmp_path / "bad.log"
    path.write_text("this is not an apache log line\n", encoding="utf-8")

    parser = GrokParser("%{COMBINEDAPACHELOG}")

    with pytest.raises(ValueError, match="did not match"):
        list(parser.parse(path))


def test_parse_skips_blank_lines(tmp_path: Path) -> None:
    line = '172.17.130.196 - - [19/Jan/2022:07:46:29 +0000] "GET / HTTP/1.1" 200 6128 "-" "-"\n'
    path = tmp_path / "with_blank.log"
    path.write_text(line + "\n" + line, encoding="utf-8")

    parser = GrokParser("%{COMBINEDAPACHELOG}")
    results = list(parser.parse(path))

    assert len(results) == 2
