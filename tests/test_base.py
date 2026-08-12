from __future__ import annotations

from pathlib import Path

from awesome_log_data.base import DatasetAdapter


def test_fake_adapter_satisfies_dataset_adapter_protocol(
    fake_adapter: type[DatasetAdapter], tmp_path: Path
) -> None:
    assert isinstance(fake_adapter, DatasetAdapter)

    sources = list(fake_adapter.discover(tmp_path))
    assert len(sources) == 1
    assert sources[0].file_name == "sample.jsonl"
