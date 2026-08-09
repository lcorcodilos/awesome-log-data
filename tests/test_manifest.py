from __future__ import annotations

import hashlib
import json
from pathlib import Path

from awesome_log_data.manifest import ManifestEntry, ManifestStore, sha256_file


def _entry(source_id: str, checksum: str = "abc123") -> ManifestEntry:
    return ManifestEntry(
        source_id=source_id,
        dataset_id="otrf",
        file_name=source_id.split("/", 1)[1],
        source_url="https://example.com/" + source_id,
        license="MIT",
        ingested_at="2026-08-09",
        checksum_sha256=checksum,
        bytes=1234,
        record_count=10,
        labeled=True,
        record_ref_type="byte_offset",
        notes="",
    )


def test_sha256_file_matches_known_hash(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_bytes(b"hello world")

    assert sha256_file(path) == hashlib.sha256(b"hello world").hexdigest()


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)
    store.upsert(_entry("otrf/a.json"))
    store.upsert(_entry("otrf/b.json"))
    store.write()

    reloaded = ManifestStore(path)

    assert reloaded.get("otrf/a.json") == _entry("otrf/a.json")
    assert reloaded.get("otrf/b.json") == _entry("otrf/b.json")


def test_write_one_json_object_per_line(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)
    store.upsert(_entry("otrf/a.json"))
    store.upsert(_entry("otrf/b.json"))
    store.write()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["source_id"] == "otrf/a.json"


def test_manifest_store_get_missing_returns_none(tmp_path: Path) -> None:
    store = ManifestStore(tmp_path / "does_not_exist.jsonl")
    assert store.get("otrf/missing.json") is None


def test_manifest_store_loads_existing_file_on_init(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    seed = ManifestStore(path)
    seed.upsert(_entry("otrf/a.json"))
    seed.write()

    store = ManifestStore(path)

    assert store.get("otrf/a.json") == _entry("otrf/a.json")


def test_write_sorts_entries_by_source_id_by_default(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)
    store.upsert(_entry("otrf/b.json"))
    store.upsert(_entry("otrf/a.json"))

    store.write()

    lines = path.read_text(encoding="utf-8").splitlines()
    ids = [json.loads(line)["source_id"] for line in lines]
    assert ids == ["otrf/a.json", "otrf/b.json"]


def test_write_preserves_insertion_order_when_sort_is_false(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)
    store.upsert(_entry("otrf/b.json"))
    store.upsert(_entry("otrf/a.json"))

    store.write(sort=False)

    lines = path.read_text(encoding="utf-8").splitlines()
    ids = [json.loads(line)["source_id"] for line in lines]
    assert ids == ["otrf/b.json", "otrf/a.json"]


def test_read_reloads_and_replaces_in_memory_entries(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    store = ManifestStore(path)
    store.upsert(_entry("otrf/a.json"))
    store.write()

    other_handle = ManifestStore(path)
    other_handle.upsert(_entry("otrf/b.json"))
    other_handle.write()

    store.read()

    assert store.get("otrf/a.json") == _entry("otrf/a.json")
    assert store.get("otrf/b.json") == _entry("otrf/b.json")
