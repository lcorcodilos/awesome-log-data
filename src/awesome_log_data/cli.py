"""cli.py <dataset_id> <path>: extract (if needed) + parse + manifest + shard.

No subcommands: fetching is out of scope (base.py assumes raw files already
exist on disk — see PLAN.md Section 1), and resolve() is available
programmatically via the registry rather than as a CLI command.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

import click

from awesome_log_data.adapters import adapter_exists, get_adapter
from awesome_log_data.base import DatasetId
from awesome_log_data.manifest import ManifestEntry, ManifestStore, compute_source_id, sha256_file
from awesome_log_data.sharded_dataset import ShardedDataset

DEFAULT_MANIFEST_PATH = Path("data/manifest.jsonl")
DEFAULT_PARSED_ROOT = Path("data/parsed")


@dataclass(frozen=True)
class IngestSummary:
    files_ingested: int
    files_skipped: int
    records_written: int


def ingest_dataset(
    dataset_id: DatasetId,
    raw_path: Path,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    parsed_root: Path = DEFAULT_PARSED_ROOT,
) -> IngestSummary:
    adapter = get_adapter(dataset_id)
    manifest = ManifestStore(manifest_path)
    dataset = ShardedDataset(parsed_root / dataset_id)

    files_ingested = 0
    files_skipped = 0
    records_written = 0

    try:
        for source in adapter.discover(raw_path):
            source_id = compute_source_id(dataset_id, source.file_name, source.path, manifest)
            if manifest.get(source_id) is not None:
                # Already ingested (compute_source_id only returns an
                # existing id when the checksum matches) — skip so a rerun
                # doesn't duplicate records into the resumed shard.
                files_skipped += 1
                continue

            record_count = 0
            for ref, parsed in source.parser.parse(source.path):
                dataset.append(source_id, ref, parsed)
                record_count += 1

            manifest.upsert(
                ManifestEntry(
                    source_id=source_id,
                    dataset_id=dataset_id,
                    file_name=source.file_name,
                    source_url=source.source_url,
                    license=source.license,
                    ingested_at=datetime.date.today().isoformat(),
                    checksum_sha256=sha256_file(source.path),
                    bytes=source.path.stat().st_size,
                    record_count=record_count,
                    labeled=source.labeled,
                    record_ref_type=source.parser.record_ref_type,
                    notes="",
                )
            )
            files_ingested += 1
            records_written += record_count
    finally:
        dataset.close()
        manifest.write()

    return IngestSummary(
        files_ingested=files_ingested,
        files_skipped=files_skipped,
        records_written=records_written,
    )


@click.command()
@click.argument("dataset_id")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def main(dataset_id: str, path: Path) -> None:
    """Ingest DATASET_ID's raw files at PATH: extract + parse + manifest + shard."""
    # Checking dataset ID here instead of click.Choice to keep it
    # live across the module's lifetime, same as the registry itself.
    if not adapter_exists(dataset_id):
        raise click.BadParameter(
            f"no adapter registered for dataset_id {dataset_id!r}",
            param_hint="'dataset_id'",
        )

    summary = ingest_dataset(dataset_id, path)
    click.echo(
        f"{dataset_id}: ingested {summary.files_ingested} file(s) "
        f"({summary.records_written} records), skipped {summary.files_skipped} "
        "already-ingested file(s)"
    )


if __name__ == "__main__":
    main()
