from __future__ import annotations

import gzip
import io
import json
import tarfile
from pathlib import Path

from awesome_log_data.adapters.flaws_cloud import FlawsCloudAdapter
from awesome_log_data.parsers.json_array_parser import JsonArrayParser


def _write_gz_json(path: Path, records: list[dict[str, object]]) -> bytes:
    return gzip.compress(json.dumps({"Records": records}).encode("utf-8"))


def _make_tar(tar_path: Path, members: dict[str, bytes]) -> None:
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "w") as tf:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))


def test_discover_extracts_tar_and_gunzips_json_gz(tmp_path: Path) -> None:
    gz_bytes = _write_gz_json(tmp_path, [{"eventName": "A"}])
    _make_tar(
        tmp_path / "flaws_cloudtrail_logs.tar",
        {"flaws_cloudtrail_logs/flaws_cloudtrail00.json.gz": gz_bytes},
    )

    sources = list(FlawsCloudAdapter.discover(tmp_path))

    assert len(sources) == 1
    source = sources[0]
    assert source.path.exists()
    assert source.path.suffix == ".json"
    assert isinstance(source.parser, JsonArrayParser)
    assert source.parser.record_ref_type == "array_index"
    assert source.labeled is True
    assert source.file_name == (
        "flaws_cloudtrail_logs/flaws_cloudtrail_logs/flaws_cloudtrail00.json"
    )


def test_discover_extracted_file_parses_to_real_records(tmp_path: Path) -> None:
    gz_bytes = _write_gz_json(tmp_path, [{"eventName": "A"}, {"eventName": "B"}])
    _make_tar(
        tmp_path / "flaws_cloudtrail_logs.tar",
        {"flaws_cloudtrail_logs/flaws_cloudtrail00.json.gz": gz_bytes},
    )

    (source,) = list(FlawsCloudAdapter.discover(tmp_path))
    records = list(source.parser.parse(source.path))

    assert [r["eventName"] for _ref, r in records] == ["A", "B"]


def test_discover_finds_multiple_gz_members(tmp_path: Path) -> None:
    gz_a = _write_gz_json(tmp_path, [{"eventName": "A"}])
    gz_b = _write_gz_json(tmp_path, [{"eventName": "B"}])
    _make_tar(
        tmp_path / "flaws_cloudtrail_logs.tar",
        {
            "flaws_cloudtrail_logs/flaws_cloudtrail00.json.gz": gz_a,
            "flaws_cloudtrail_logs/flaws_cloudtrail01.json.gz": gz_b,
        },
    )

    sources = list(FlawsCloudAdapter.discover(tmp_path))

    assert {s.file_name for s in sources} == {
        "flaws_cloudtrail_logs/flaws_cloudtrail_logs/flaws_cloudtrail00.json",
        "flaws_cloudtrail_logs/flaws_cloudtrail_logs/flaws_cloudtrail01.json",
    }
