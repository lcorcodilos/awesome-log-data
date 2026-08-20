from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

import pytest
from click.testing import CliRunner

from awesome_log_data import adapters
from awesome_log_data.base import DatasetAdapter, DatasetId, SourceFile
from awesome_log_data.cli import IngestSummary, ingest_dataset, main
from awesome_log_data.manifest import ManifestStore
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser
from awesome_log_data.sharded_dataset import ShardedDataset

OTRF = "otrf"


def _fake_adapter(sources: list[SourceFile]) -> type[DatasetAdapter]:
    "Builds a fresh adapter class per call, with sources baked in by closure."

    class _FakeAdapter:
        dataset_id: ClassVar[DatasetId] = OTRF

        @staticmethod
        def discover(root: Path) -> Iterator[SourceFile]:
            yield from sources

    return _FakeAdapter


@pytest.fixture(autouse=True)
def _clean_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapters, "_REGISTRY", {})


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def test_ingest_dataset_writes_manifest_and_shards(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    source_path = raw / "sample.jsonl"
    _write_jsonl(source_path, [{"eventName": "A"}, {"eventName": "B"}])

    source = SourceFile(
        file_name="sample.jsonl",
        path=source_path,
        parser=JsonLinesParser(),
        source_url="https://example.com/sample.jsonl",
        license="MIT",
        labeled=False,
    )
    adapters.register(_fake_adapter([source]))

    manifest_path = tmp_path / "manifest.jsonl"
    parsed_root = tmp_path / "parsed"

    summary = ingest_dataset(OTRF, raw, manifest_path=manifest_path, parsed_root=parsed_root)

    assert summary.files_ingested == 1
    assert summary.files_skipped == 0
    assert summary.records_written == 2

    manifest = ManifestStore(manifest_path)
    entry = manifest.get("otrf/sample.jsonl")
    assert entry is not None
    assert entry.dataset_id == "otrf"
    assert entry.file_name == "sample.jsonl"
    assert entry.record_count == 2
    assert entry.labeled is False
    assert entry.record_ref_type == "byte_offset"

    dataset = ShardedDataset(parsed_root / "otrf")
    assert len(dataset) == 2
    assert dataset[0] == {"eventName": "A"}
    assert dataset[1] == {"eventName": "B"}


def test_ingest_dataset_is_idempotent_on_rerun(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    source_path = raw / "sample.jsonl"
    _write_jsonl(source_path, [{"eventName": "A"}])

    source = SourceFile(
        file_name="sample.jsonl",
        path=source_path,
        parser=JsonLinesParser(),
        source_url="https://example.com/sample.jsonl",
        license="MIT",
        labeled=False,
    )
    adapters.register(_fake_adapter([source]))

    manifest_path = tmp_path / "manifest.jsonl"
    parsed_root = tmp_path / "parsed"

    ingest_dataset(OTRF, raw, manifest_path=manifest_path, parsed_root=parsed_root)
    second = ingest_dataset(OTRF, raw, manifest_path=manifest_path, parsed_root=parsed_root)

    assert second.files_ingested == 0
    assert second.files_skipped == 1
    assert second.records_written == 0

    manifest = ManifestStore(manifest_path)
    assert len(list(manifest)) == 1

    dataset = ShardedDataset(parsed_root / "otrf")
    assert len(dataset) == 1


def test_ingest_dataset_interleaves_multiple_source_files(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    path_a = raw / "a.jsonl"
    path_b = raw / "b.jsonl"
    _write_jsonl(path_a, [{"i": 0}])
    _write_jsonl(path_b, [{"i": 1}])

    sources = [
        SourceFile(
            file_name="a.jsonl",
            path=path_a,
            parser=JsonLinesParser(),
            source_url="https://example.com/a",
            license="MIT",
            labeled=False,
        ),
        SourceFile(
            file_name="b.jsonl",
            path=path_b,
            parser=JsonLinesParser(),
            source_url="https://example.com/b",
            license="MIT",
            labeled=False,
        ),
    ]
    adapters.register(_fake_adapter(sources))

    manifest_path = tmp_path / "manifest.jsonl"
    parsed_root = tmp_path / "parsed"

    ingest_dataset(OTRF, raw, manifest_path=manifest_path, parsed_root=parsed_root)

    manifest = ManifestStore(manifest_path)
    assert manifest.get("otrf/a.jsonl") is not None
    assert manifest.get("otrf/b.jsonl") is not None

    dataset = ShardedDataset(parsed_root / "otrf")
    assert len(dataset) == 2
    assert {entry.source_id for entry in dataset.index} == {"otrf/a.jsonl", "otrf/b.jsonl"}


def test_main_parses_argv_and_invokes_ingest_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # dataset_id is validated against the registry inside main() itself
    # (not click.Choice — see cli.py), so it still has to actually be
    # registered to pass, even though ingest_dataset is mocked out below
    # and never touches this adapter's behavior.
    adapters.register(_fake_adapter([]))

    calls: list[tuple[DatasetId, Path]] = []

    def _fake_ingest(dataset_id: DatasetId, raw_path: Path, **_: object) -> IngestSummary:
        calls.append((dataset_id, raw_path))
        return IngestSummary(files_ingested=0, files_skipped=0, records_written=0)

    monkeypatch.setattr("awesome_log_data.cli.ingest_dataset", _fake_ingest)

    result = CliRunner().invoke(main, [OTRF, str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert calls == [(OTRF, tmp_path)]


def test_main_rejects_unknown_dataset_id(tmp_path: Path) -> None:
    # Registering a real adapter first proves this is discriminating by
    # dataset_id, not just rejecting everything because the registry is
    # empty.
    adapters.register(_fake_adapter([]))

    result = CliRunner().invoke(main, ["not_a_real_dataset", str(tmp_path)])

    assert result.exit_code != 0


def test_main_rejects_nonexistent_path() -> None:
    adapters.register(_fake_adapter([]))

    result = CliRunner().invoke(main, [OTRF, "/no/such/path/exists"])

    assert result.exit_code != 0
