from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from awesome_log_data.adapters.otrf import OtrfAdapter
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


def test_discover_raises_when_zip_does_not_contain_exactly_one_json(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("a.json", "{}")
        zf.writestr("b.json", "{}")

    with pytest.raises(ValueError, match="expected exactly one"):
        list(OtrfAdapter.discover(tmp_path))
