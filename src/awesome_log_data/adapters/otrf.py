"""OTRF Security Datasets (Mordor) adapter.

Raw files are zips scattered under category subdirectories (e.g.
datasets/atomic/cloud/aws/host/*.zip), each containing exactly one NDJSON
file — confirmed against a real sample (ec2_proxy_s3_exfiltration.zip ->
ec2_proxy_s3_exfiltration_2020-09-14011940.json). discover() extracts each
zip into a sibling directory (named after the zip, extension stripped) and
yields the inner JSON file as a JsonLinesParser source, keyed by its path
relative to root so files with the same basename in different categories
don't collide in the manifest.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from awesome_log_data.adapters import register
from awesome_log_data.base import DatasetId, SourceFile
from awesome_log_data.extractor import extract_zip
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser


@register
class OtrfAdapter:
    dataset_id: ClassVar[DatasetId] = "otrf"
    source_url: ClassVar[str] = "https://github.com/OTRF/Security-Datasets"
    license: ClassVar[str] = "GPL-3.0"

    @staticmethod
    def discover(root: Path) -> Iterator[SourceFile]:
        for zip_path in sorted(root.rglob("*.zip")):
            extracted = extract_zip(zip_path)
            json_files = [p for p in extracted if p.suffix == ".json"]
            if len(json_files) != 1:
                raise ValueError(
                    f"expected exactly one .json file in {zip_path}, found {len(json_files)}"
                )
            json_path = json_files[0]
            yield SourceFile(
                file_name=json_path.relative_to(root).as_posix(),
                path=json_path,
                parser=JsonLinesParser(),
                source_url=OtrfAdapter.source_url,
                license=OtrfAdapter.license,
                labeled=True,
            )
