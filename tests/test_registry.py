from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

import pytest

from awesome_log_data import adapters
from awesome_log_data.adapters import get_adapter, register
from awesome_log_data.base import DatasetAdapter, DatasetId, SourceFile

OTRF = "otrf"


@pytest.fixture(autouse=True)
def _clean_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapters, "_REGISTRY", {})


def test_get_adapter_raises_lookup_error_when_unregistered() -> None:
    with pytest.raises(LookupError):
        get_adapter(OTRF)


def test_register_then_get_adapter_round_trips(fake_adapter: type[DatasetAdapter]) -> None:
    register(fake_adapter)

    assert get_adapter(OTRF) is fake_adapter


def test_register_returns_class_unchanged_for_decorator_use() -> None:
    @register
    class _AnotherAdapter:
        dataset_id: ClassVar[DatasetId] = "another"

        @staticmethod
        def discover(root: Path) -> Iterator[SourceFile]:
            yield from ()

    assert get_adapter("another") is _AnotherAdapter


def test_register_raises_on_duplicate_dataset_id(fake_adapter: type[DatasetAdapter]) -> None:
    register(fake_adapter)

    with pytest.raises(ValueError, match="already registered"):
        register(fake_adapter)
