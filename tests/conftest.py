from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

import pytest

from awesome_log_data.base import DatasetAdapter, DatasetId, SourceFile
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser


class _FakeAdapter:
    dataset_id: ClassVar[DatasetId] = "otrf"

    @staticmethod
    def discover(root: Path) -> Iterator[SourceFile]:
        yield SourceFile(
            file_name="sample.jsonl",
            path=root / "sample.jsonl",
            parser=JsonLinesParser(),
            source_url="https://example.com/sample.jsonl",
            license="MIT",
            labeled=False,
        )


@pytest.fixture
def fake_adapter() -> type[DatasetAdapter]:
    return _FakeAdapter
