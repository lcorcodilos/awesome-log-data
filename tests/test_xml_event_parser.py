from __future__ import annotations

from pathlib import Path

import pytest

from awesome_log_data.parsers.xml_event_parser import XmlEventParser

_TWO_EVENTS = (
    b"<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'>"
    b"<System><EventID>4688</EventID></System>"
    b"</Event>\n"
    b"<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'>"
    b"<System><EventID>4689</EventID></System>"
    b"</Event>\n"
)


def test_parse_yields_one_record_per_event(tmp_path: Path) -> None:
    path = tmp_path / "events.log"
    path.write_bytes(_TWO_EVENTS)

    parser = XmlEventParser()
    results = list(parser.parse(path))

    assert len(results) == 2
    assert parser.record_ref_type == "byte_offset"
    assert results[0][1]["Event"]["System"]["EventID"] == "4688"
    assert results[1][1]["Event"]["System"]["EventID"] == "4689"


def test_parse_handles_embedded_newlines_inside_a_single_event(tmp_path: Path) -> None:
    # Windows Event XML fields (e.g. Privileges) can contain real newlines,
    # so records must be split on </Event> boundaries, not on \n.
    data = (
        b"<Event xmlns='urn:x'><System><EventID>1</EventID></System>"
        b"<EventData><Data Name='Privileges'>SeDebugPrivilege\nSeBackupPrivilege</Data></EventData>"
        b"</Event>\n"
    )
    path = tmp_path / "multiline.log"
    path.write_bytes(data)

    parser = XmlEventParser()
    results = list(parser.parse(path))

    assert len(results) == 1
    assert "SeDebugPrivilege" in results[0][1]["Event"]["EventData"]["Data"]["#text"]


def test_resolve_returns_record_at_ref(tmp_path: Path) -> None:
    path = tmp_path / "events.log"
    path.write_bytes(_TWO_EVENTS)

    parser = XmlEventParser()
    results = list(parser.parse(path))

    for ref, expected in results:
        assert parser.resolve(path, ref) == expected


def test_resolve_raises_lookup_error_for_unknown_ref(tmp_path: Path) -> None:
    path = tmp_path / "events.log"
    path.write_bytes(_TWO_EVENTS)

    parser = XmlEventParser()

    with pytest.raises(LookupError):
        parser.resolve(path, 99999)


def test_parse_yields_nothing_for_a_file_with_no_events(tmp_path: Path) -> None:
    path = tmp_path / "empty.log"
    path.write_bytes(b"")

    parser = XmlEventParser()
    results = list(parser.parse(path))

    assert results == []


def test_parse_escapes_unescaped_ampersands_in_field_text(tmp_path: Path) -> None:
    # Some source exports don't XML-escape command lines, e.g. `2>&1` or
    # `&($ShellId[1] + 'ex')`, which expat otherwise rejects outright.
    data = (
        b"<Event xmlns='urn:x'><System><EventID>1</EventID></System>"
        b"<EventData><Data Name='CommandLine'>foo.exe 2>&1 &amp; bar</Data></EventData>"
        b"</Event>\n"
    )
    path = tmp_path / "ampersand.log"
    path.write_bytes(data)

    parser = XmlEventParser()
    results = list(parser.parse(path))

    assert len(results) == 1
    assert results[0][1]["Event"]["EventData"]["Data"]["#text"] == "foo.exe 2>&1 & bar"


def test_parse_skips_truncated_event_without_corrupting_the_next_record(tmp_path: Path) -> None:
    # A truncated record (no closing </Event>, e.g. cut off mid-attribute)
    # must not swallow the following, well-formed record into one bad match.
    data = (
        b"<Event xmlns='urn:x'><System><EventID>1</EventID></System>"
        b"<EventData><Data Name='CommandLine'>truncated mid-valu"
        b"<Event xmlns='urn:x'><System><EventID>2</EventID></System></Event>\n"
    )
    path = tmp_path / "truncated.log"
    path.write_bytes(data)

    parser = XmlEventParser()
    results = list(parser.parse(path))

    assert len(results) == 1
    assert results[0][1]["Event"]["System"]["EventID"] == "2"
