from __future__ import annotations

from pathlib import Path

import pytest

from awesome_log_data.parsers.auditd_parser import AuditdParser

FIXTURE = Path(__file__).parent / "data" / "audit.log"


def test_parse_yields_one_record_per_line() -> None:
    parser = AuditdParser()
    results = list(parser.parse(FIXTURE))

    with open(FIXTURE, encoding="utf-8") as f:
        expected_count = sum(1 for line in f if line.strip())
    assert len(results) == expected_count
    assert parser.record_ref_type == "byte_offset"


def test_parse_extracts_type_epoch_and_audit_id() -> None:
    parser = AuditdParser()
    _ref, first = next(iter(parser.parse(FIXTURE)))

    assert first["type"] == "USER_ACCT"
    assert first["epoch"] == "1642205341.337"
    assert first["audit_id"] == "357"


def test_parse_tokenizes_simple_key_value_tail() -> None:
    parser = AuditdParser()
    records = [r for _ref, r in parser.parse(FIXTURE)]

    login = next(r for r in records if r["type"] == "LOGIN")
    assert login["pid"] == "4733"
    assert login["uid"] == "0"
    # Hyphenated keys (old-auid, old-ses) must survive as their own fields,
    # distinct from the similarly-named auid/ses.
    assert login["old-auid"] == "4294967295"
    assert login["old-ses"] == "4294967295"
    assert login["ses"] == "62"
    assert login["res"] == "1"


def test_parse_unquotes_double_quoted_values() -> None:
    parser = AuditdParser()
    records = [r for _ref, r in parser.parse(FIXTURE)]

    syscall = next(r for r in records if r["type"] == "SYSCALL")
    assert syscall["comm"] == "apparmor_parser"
    assert syscall["exe"] == "/sbin/apparmor_parser"
    assert syscall["a0"] == "6"


def test_parse_keeps_nested_single_quoted_msg_without_colliding_with_prefix(
) -> None:
    parser = AuditdParser()
    records = [r for _ref, r in parser.parse(FIXTURE)]

    cred_disp = next(r for r in records if r["type"] == "CRED_DISP")
    # The prefix's own "msg=audit(...)" is captured as epoch/audit_id, so the
    # trailing msg='...' (PAM detail) doesn't get silently overwritten.
    assert cred_disp["epoch"] == "1642205341.345"
    assert cred_disp["msg"] == (
        'op=PAM:setcred acct="root" exe="/usr/sbin/cron" hostname=? addr=? '
        "terminal=cron res=success"
    )


def test_resolve_returns_record_at_ref() -> None:
    parser = AuditdParser()
    results = list(parser.parse(FIXTURE))

    for ref, expected in results:
        assert parser.resolve(FIXTURE, ref) == expected


def test_parse_raises_on_unmatched_line(tmp_path: Path) -> None:
    path = tmp_path / "bad.log"
    path.write_text("this is not an auditd log line\n", encoding="utf-8")

    parser = AuditdParser()

    with pytest.raises(ValueError, match="did not match"):
        list(parser.parse(path))


def test_parse_skips_blank_lines(tmp_path: Path) -> None:
    line = "type=LOGIN msg=audit(1642205341.341:359): pid=4733 uid=0 res=1\n"
    path = tmp_path / "with_blank.log"
    path.write_text(line + "\n" + line, encoding="utf-8")

    parser = AuditdParser()
    results = list(parser.parse(path))

    assert len(results) == 2
