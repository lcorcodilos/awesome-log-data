"""EVTX-ATTACK-SAMPLES adapter.

Raw files are .evtx files nested under per-technique category directories
(e.g. Discovery/, Persistence/) — no extraction step. Files are keyed by
their path relative to root rather than basename alone, since sample file
names repeat across category directories.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from awesome_log_data.adapters import register
from awesome_log_data.base import DatasetId, SourceFile
from awesome_log_data.parsers.evtx_parser import EvtxParser


@register
class EvtxAttackSamplesAdapter:
    dataset_id: ClassVar[DatasetId] = "evtx_attack_samples"
    source_url: ClassVar[str] = "https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES"
    license: ClassVar[str] = "GPL-3.0"

    @staticmethod
    def discover(root: Path) -> Iterator[SourceFile]:
        for evtx_path in sorted(root.rglob("*.evtx")):
            yield SourceFile(
                file_name=evtx_path.relative_to(root).as_posix(),
                path=evtx_path,
                parser=EvtxParser(),
                source_url=EvtxAttackSamplesAdapter.source_url,
                license=EvtxAttackSamplesAdapter.license,
                labeled=True,
            )
