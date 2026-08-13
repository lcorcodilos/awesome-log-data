"""flaws.cloud / flaws2.cloud (Scott Piper) adapter.

Raw input is a single .tar containing flaws_cloudtrail_logs/*.json.gz, each
a standard CloudTrail S3 export ({"Records": [...]}) — confirmed against the
real file. discover() extracts the tar, then gunzips each .json.gz member
(JsonArrayParser reads plain files, it doesn't decompress on its own), both
persistently and idempotently via the shared extractor helpers.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from awesome_log_data.adapters import register
from awesome_log_data.base import DatasetId, SourceFile
from awesome_log_data.extractor import extract_tar, gunzip
from awesome_log_data.parsers.json_array_parser import JsonArrayParser


@register
class FlawsCloudAdapter:
    dataset_id: ClassVar[DatasetId] = "flaws_cloud"
    source_url: ClassVar[str] = "https://summitroute.com/downloads/flaws_cloudtrail_logs.tar"
    # No explicit license/terms stated on the publishing page for this
    # dataset (unlike OTRF/EVTX-ATTACK-SAMPLES, which are GitHub repos with
    # LICENSE files) — recorded honestly rather than assuming one.
    license: ClassVar[str] = "unspecified"

    @staticmethod
    def discover(root: Path) -> Iterator[SourceFile]:
        for tar_path in sorted(root.rglob("*.tar")):
            extracted = extract_tar(tar_path)
            for gz_path in sorted(p for p in extracted if p.suffix == ".gz"):
                json_path = gunzip(gz_path)
                yield SourceFile(
                    file_name=json_path.relative_to(root).as_posix(),
                    path=json_path,
                    parser=JsonArrayParser(),
                    source_url=FlawsCloudAdapter.source_url,
                    license=FlawsCloudAdapter.license,
                    labeled=True,
                )
