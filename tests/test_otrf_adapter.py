from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from awesome_log_data.adapters.otrf import OtrfAdapter
from awesome_log_data.parsers.auditd_parser import AuditdParser
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser

FIXTURE_ZIP = Path(__file__).parent / "fixtures" / "otrf" / "ec2_proxy_s3_exfiltration.zip"


def _copy_fixture_into(raw_root: Path, relative: str) -> Path:
    dest = raw_root / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_ZIP, dest)
    return dest


def test_discover_finds_nested_zip_and_extracts_ndjson(tmp_path: Path) -> None:
    _copy_fixture_into(tmp_path, "datasets/atomic/cloud/aws/host/ec2_proxy_s3_exfiltration.zip")

    sources = list(OtrfAdapter.discover(tmp_path))

    assert len(sources) == 1
    source = sources[0]
    assert source.path.exists()
    assert source.path.suffix == ".json"
    assert isinstance(source.parser, JsonLinesParser)
    assert source.parser.record_ref_type == "byte_offset"
    assert source.license == "GPL-3.0"
    assert source.labeled is True
    assert source.file_name == (
        "datasets/atomic/cloud/aws/host/ec2_proxy_s3_exfiltration/"
        "ec2_proxy_s3_exfiltration_2020-09-14011940.json"
    )


def test_discover_extracted_file_parses_to_real_records(tmp_path: Path) -> None:
    _copy_fixture_into(tmp_path, "ec2_proxy_s3_exfiltration.zip")

    (source,) = list(OtrfAdapter.discover(tmp_path))
    records = list(source.parser.parse(source.path))

    assert len(records) == 103
    for _ref, record in records:
        assert "eventName" in record


def test_discover_finds_multiple_zips_recursively(tmp_path: Path) -> None:
    _copy_fixture_into(tmp_path, "a/one.zip")
    _copy_fixture_into(tmp_path, "b/two.zip")

    sources = list(OtrfAdapter.discover(tmp_path))

    assert {s.file_name for s in sources} == {
        "a/one/ec2_proxy_s3_exfiltration_2020-09-14011940.json",
        "b/two/ec2_proxy_s3_exfiltration_2020-09-14011940.json",
    }


def test_discover_raises_when_zip_contains_more_than_one_json(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("a.json", "{}")
        zf.writestr("b.json", "{}")

    with pytest.raises(ValueError, match="expected at most one"):
        list(OtrfAdapter.discover(tmp_path))


def test_discover_ignores_macosx_junk_alongside_the_real_json(tmp_path: Path) -> None:
    zip_path = tmp_path / "with_junk.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("real.json", '{"eventName": "A"}\n')
        zf.writestr("__MACOSX/._real.json", b"\x00\x05junk")

    sources = list(OtrfAdapter.discover(tmp_path))

    assert len(sources) == 1
    assert sources[0].path.name == "real.json"


def test_discover_yields_nothing_for_a_zip_with_only_pcap_content(tmp_path: Path) -> None:
    zip_path = tmp_path / "capture_only.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("capture.pcap", b"\x00\x01\x02")
        zf.writestr("capture.pcap.sha1sum", "deadbeef  capture.pcap\n")

    sources = list(OtrfAdapter.discover(tmp_path))

    assert sources == []


def test_discover_yields_nothing_for_a_zip_with_only_csv_content(tmp_path: Path) -> None:
    zip_path = tmp_path / "csv_only.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data.csv", "a,b\n1,2\n")

    sources = list(OtrfAdapter.discover(tmp_path))

    assert sources == []


def test_discover_finds_single_auditd_log_file(tmp_path: Path) -> None:
    zip_path = tmp_path / "sh_arp_cache.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "sh_arp_cache_2020-11-10074812.log",
            "type=SYSCALL msg=audit(1604994496.155:92733): "
            'arch=c000003e syscall=59 success=yes comm="arp"\n',
        )

    (source,) = list(OtrfAdapter.discover(tmp_path))

    assert isinstance(source.parser, AuditdParser)
    records = list(source.parser.parse(source.path))
    assert records[0][1]["type"] == "SYSCALL"


def test_discover_finds_json_lines_log_files_but_skips_real_tsv_zeek_logs(
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "mixed_zeek_logs.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("conn.log", '{"@stream": "conn", "id_orig_h": "10.0.0.4"}\n')
        zf.writestr(
            "capture_loss.log",
            "#separator \\x09\n#path\tcapture_loss\n1588317394.364058\ttest-nsm\tzeek\t29\n",
        )

    sources = list(OtrfAdapter.discover(tmp_path))

    assert len(sources) == 1
    assert sources[0].path.name == "conn.log"
    assert isinstance(sources[0].parser, JsonLinesParser)
