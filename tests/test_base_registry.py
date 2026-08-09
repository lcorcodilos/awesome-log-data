from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from awesome_log_data import base
from awesome_log_data.base import (
    DatasetAdapter,
    SourceFile,
    get_adapter,
    register,
)
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser

OTRF = "otrf"


class _FakeAdapter:
    dataset_id = OTRF

    def discover(self, root: Path) -> Iterator[SourceFile]:
        yield SourceFile(
            file_name="sample.jsonl",
            path=root / "sample.jsonl",
            parser=JsonLinesParser(),
            source_url="https://example.com/sample.jsonl",
            license="MIT",
            labeled=False,
        )


@pytest.fixture(autouse=True)
def _clean_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base, "_REGISTRY", {})


def test_get_adapter_raises_lookup_error_when_unregistered() -> None:
    with pytest.raises(LookupError):
        get_adapter(OTRF)


def test_register_then_get_adapter_round_trips() -> None:
    adapter = _FakeAdapter()
    register(adapter)

    assert get_adapter(OTRF) is adapter


def test_register_raises_on_duplicate_dataset_id() -> None:
    register(_FakeAdapter())

    with pytest.raises(ValueError, match="already registered"):
        register(_FakeAdapter())


def test_fake_adapter_satisfies_dataset_adapter_protocol(tmp_path: Path) -> None:
    adapter: DatasetAdapter = _FakeAdapter()

    assert isinstance(adapter, DatasetAdapter)

    sources = list(adapter.discover(tmp_path))
    assert len(sources) == 1
    assert sources[0].file_name == "sample.jsonl"
