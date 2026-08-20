from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from awesome_log_data.sharded_dataset import ShardedDataset


def test_append_writes_bare_parsed_records_to_shard_file(tmp_path: Path) -> None:
    ds = ShardedDataset(tmp_path, shard_size=10)
    ds.append("otrf/a.json", 0, {"eventName": "A"})
    ds.append("otrf/a.json", 42, {"eventName": "B"})
    ds.close()

    shard_path = tmp_path / "00000.jsonl"
    lines = [json.loads(line) for line in shard_path.read_text(encoding="utf-8").splitlines()]

    assert lines == [{"eventName": "A"}, {"eventName": "B"}]


def test_append_rolls_over_to_new_shard_when_full(tmp_path: Path) -> None:
    ds = ShardedDataset(tmp_path, shard_size=2)
    for i in range(5):
        ds.append("otrf/a.json", i, {"i": i})
    ds.close()

    shard_files = sorted(p.name for p in tmp_path.glob("[0-9]*.jsonl"))
    assert shard_files == ["00000.jsonl", "00001.jsonl", "00002.jsonl"]

    counts = [
        len((tmp_path / name).read_text(encoding="utf-8").splitlines()) for name in shard_files
    ]
    assert counts == [2, 2, 1]


def test_close_writes_index_file_with_one_entry_per_record(tmp_path: Path) -> None:
    ds = ShardedDataset(tmp_path, shard_size=2)
    for i in range(3):
        ds.append("otrf/a.json", i, {"i": i})
    ds.close()

    df = pl.read_parquet(tmp_path / "shard_index.parquet")

    assert len(df) == 3
    assert df["shard_id"].to_list() == [0, 0, 1]
    assert all(v == 0 for v in df["source_id"].to_list())
    assert df["record_ref"].to_list() == [0, 1, 2]

    source_ids_path = tmp_path / "source_ids.jsonl"
    lines = source_ids_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == ["otrf/a.json"]


def test_context_manager_closes_and_flushes_index(tmp_path: Path) -> None:
    with ShardedDataset(tmp_path, shard_size=10) as ds:
        ds.append("otrf/a.json", 0, {"i": 0})

    assert (tmp_path / "shard_index.parquet").exists()


def test_getitem_returns_correct_record_by_global_index(tmp_path: Path) -> None:
    with ShardedDataset(tmp_path, shard_size=2) as ds:
        for i in range(5):
            ds.append("otrf/a.json", i, {"i": i})

    reader = ShardedDataset(tmp_path, shard_size=2)

    assert len(reader) == 5
    for i in range(5):
        record = reader[i]
        assert record == {"i": i}
        assert reader.source_ids[reader.index[i].source_id] == "otrf/a.json"
        assert reader.index[i].record_ref == i


def test_indices_for_source_filters_correctly(tmp_path: Path) -> None:
    with ShardedDataset(tmp_path, shard_size=3) as ds:
        ds.append("otrf/a.json", 0, {"i": 0})
        ds.append("otrf/b.json", 0, {"i": 1})
        ds.append("otrf/a.json", 1, {"i": 2})
        ds.append("otrf/b.json", 1, {"i": 3})

    reader = ShardedDataset(tmp_path, shard_size=3)

    a_indices = reader.indices_for_source("otrf/a.json")
    assert [reader[i]["i"] for i in a_indices] == [0, 2]

    b_indices = reader.indices_for_source("otrf/b.json")
    assert [reader[i]["i"] for i in b_indices] == [1, 3]


def test_resume_appending_after_reopen(tmp_path: Path) -> None:
    with ShardedDataset(tmp_path, shard_size=3) as ds:
        ds.append("otrf/a.json", 0, {"i": 0})
        ds.append("otrf/a.json", 1, {"i": 1})

    # Last shard (00000.jsonl) has 2 of 3 slots filled — resuming must append
    # into it rather than overwrite it or skip straight to a new shard.
    with ShardedDataset(tmp_path, shard_size=3) as ds:
        ds.append("otrf/b.json", 0, {"i": 2})
        ds.append("otrf/b.json", 1, {"i": 3})

    shard_files = sorted(p.name for p in tmp_path.glob("[0-9]*.jsonl"))
    assert shard_files == ["00000.jsonl", "00001.jsonl"]

    reader = ShardedDataset(tmp_path, shard_size=3)
    assert len(reader) == 4
    assert [reader[i]["i"] for i in range(4)] == [0, 1, 2, 3]


def test_resume_when_last_shard_was_filled_to_exact_boundary(tmp_path: Path) -> None:
    with ShardedDataset(tmp_path, shard_size=2) as ds:
        ds.append("otrf/a.json", 0, {"i": 0})
        ds.append("otrf/a.json", 1, {"i": 1})

    # 00000.jsonl already has exactly shard_size records — resuming must
    # start a fresh shard, not overfill the existing one.
    with ShardedDataset(tmp_path, shard_size=2) as ds:
        ds.append("otrf/b.json", 0, {"i": 2})

    shard_files = sorted(p.name for p in tmp_path.glob("[0-9]*.jsonl"))
    assert shard_files == ["00000.jsonl", "00001.jsonl"]

    first_shard_lines = (tmp_path / "00000.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(first_shard_lines) == 2

    reader = ShardedDataset(tmp_path, shard_size=2)
    assert len(reader) == 3
    assert [reader[i]["i"] for i in range(3)] == [0, 1, 2]


def test_repeated_source_id_reuses_the_same_interned_int(tmp_path: Path) -> None:
    with ShardedDataset(tmp_path, shard_size=10) as ds:
        ds.append("otrf/a.json", 0, {"i": 0})
        ds.append("otrf/a.json", 1, {"i": 1})
        ds.append("otrf/a.json", 2, {"i": 2})

    reader = ShardedDataset(tmp_path, shard_size=10)
    assert reader.source_ids == ["otrf/a.json"]
    assert [entry.source_id for entry in reader.index] == [0, 0, 0]


def test_distinct_source_ids_get_sequential_ids_in_first_seen_order(tmp_path: Path) -> None:
    with ShardedDataset(tmp_path, shard_size=10) as ds:
        ds.append("otrf/b.json", 0, {"i": 0})
        ds.append("otrf/a.json", 0, {"i": 1})
        ds.append("otrf/b.json", 1, {"i": 2})

    reader = ShardedDataset(tmp_path, shard_size=10)
    assert reader.source_ids == ["otrf/b.json", "otrf/a.json"]
    assert [entry.source_id for entry in reader.index] == [0, 1, 0]


def test_resuming_appends_new_source_ids_after_existing_ones(tmp_path: Path) -> None:
    with ShardedDataset(tmp_path, shard_size=10) as ds:
        ds.append("otrf/a.json", 0, {"i": 0})

    with ShardedDataset(tmp_path, shard_size=10) as ds:
        ds.append("otrf/b.json", 0, {"i": 1})
        ds.append("otrf/a.json", 1, {"i": 2})

    reader = ShardedDataset(tmp_path, shard_size=10)
    assert reader.source_ids == ["otrf/a.json", "otrf/b.json"]
    assert [entry.source_id for entry in reader.index] == [0, 1, 0]


def test_indices_for_source_returns_empty_for_unknown_source_id(tmp_path: Path) -> None:
    with ShardedDataset(tmp_path, shard_size=10) as ds:
        ds.append("otrf/a.json", 0, {"i": 0})

    reader = ShardedDataset(tmp_path, shard_size=10)
    assert reader.indices_for_source("otrf/never-appended.json") == []
