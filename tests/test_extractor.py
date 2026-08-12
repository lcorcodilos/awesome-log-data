from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from pathlib import Path

from awesome_log_data.extractor import extract_tar, extract_zip, gunzip


def _make_zip(zip_path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)


def _make_tar(tar_path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(tar_path, "w") as tf:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))


def test_extract_zip_extracts_all_members(tmp_path: Path) -> None:
    zip_path = tmp_path / "sample.zip"
    _make_zip(zip_path, {"a.json": "{}", "nested/b.json": "{}"})
    dest_dir = tmp_path / "sample"

    extracted = extract_zip(zip_path, dest_dir)

    assert {p.relative_to(dest_dir).as_posix() for p in extracted} == {"a.json", "nested/b.json"}
    for p in extracted:
        assert p.is_file()


def test_extract_zip_skips_reextraction_when_dest_dir_exists(tmp_path: Path) -> None:
    zip_path = tmp_path / "sample.zip"
    _make_zip(zip_path, {"a.json": "{}"})
    dest_dir = tmp_path / "sample"

    first = extract_zip(zip_path, dest_dir)
    # Mutate the extracted file so we can prove a second call left it alone.
    (dest_dir / "a.json").write_text("mutated")

    second = extract_zip(zip_path, dest_dir)

    assert first == second
    assert (dest_dir / "a.json").read_text() == "mutated"


def test_extract_zip_defaults_dest_dir_to_stem_sibling(tmp_path: Path) -> None:
    zip_path = tmp_path / "sample.zip"
    _make_zip(zip_path, {"a.json": "{}"})

    extracted = extract_zip(zip_path)

    assert extracted == [tmp_path / "sample" / "a.json"]


def test_extract_tar_extracts_all_members(tmp_path: Path) -> None:
    tar_path = tmp_path / "sample.tar"
    _make_tar(tar_path, {"a.json": b"{}", "nested/b.json": b"{}"})
    dest_dir = tmp_path / "sample"

    extracted = extract_tar(tar_path, dest_dir)

    assert {p.relative_to(dest_dir).as_posix() for p in extracted} == {"a.json", "nested/b.json"}
    for p in extracted:
        assert p.is_file()


def test_extract_tar_skips_reextraction_when_dest_dir_exists(tmp_path: Path) -> None:
    tar_path = tmp_path / "sample.tar"
    _make_tar(tar_path, {"a.json": b"{}"})
    dest_dir = tmp_path / "sample"

    first = extract_tar(tar_path, dest_dir)
    (dest_dir / "a.json").write_text("mutated")

    second = extract_tar(tar_path, dest_dir)

    assert first == second
    assert (dest_dir / "a.json").read_text() == "mutated"


def test_extract_tar_defaults_dest_dir_to_stem_sibling(tmp_path: Path) -> None:
    tar_path = tmp_path / "sample.tar"
    _make_tar(tar_path, {"a.json": b"{}"})

    extracted = extract_tar(tar_path)

    assert extracted == [tmp_path / "sample" / "a.json"]


def test_gunzip_decompresses_to_dest_path(tmp_path: Path) -> None:
    gz_path = tmp_path / "sample.json.gz"
    with gzip.open(gz_path, "wb") as f:
        f.write(b'{"Records": []}')
    dest_path = tmp_path / "sample.json"

    result = gunzip(gz_path, dest_path)

    assert result == dest_path
    assert dest_path.read_bytes() == b'{"Records": []}'


def test_gunzip_skips_redecompression_when_dest_path_exists(tmp_path: Path) -> None:
    gz_path = tmp_path / "sample.json.gz"
    with gzip.open(gz_path, "wb") as f:
        f.write(b'{"Records": []}')
    dest_path = tmp_path / "sample.json"

    gunzip(gz_path, dest_path)
    dest_path.write_bytes(b"mutated")

    result = gunzip(gz_path, dest_path)

    assert result == dest_path
    assert dest_path.read_bytes() == b"mutated"


def test_gunzip_defaults_dest_path_to_gz_stem_sibling(tmp_path: Path) -> None:
    gz_path = tmp_path / "sample.json.gz"
    with gzip.open(gz_path, "wb") as f:
        f.write(b"{}")

    result = gunzip(gz_path)

    assert result == tmp_path / "sample.json"
    assert result.read_bytes() == b"{}"
