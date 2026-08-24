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
import logfire

from awesome_log_data.adapters import adapter_exists, get_adapter
from awesome_log_data.base import DatasetId
from awesome_log_data.manifest import ManifestEntry, ManifestStore, compute_source_id, sha256_file
from awesome_log_data.sharded_dataset import ShardedDataset

logfire.configure(send_to_logfire=False)

DEFAULT_MANIFEST_PATH = Path("data/manifest.jsonl")
DEFAULT_PARSED_ROOT = Path("data/parsed")


@dataclass(frozen=True)
class IngestSummary:
    files_ingested: int
    files_skipped: int
    records_written: int
    records_dropped: int


def _count_fields(value: object) -> int:
    """Number of key-value pairs in a (possibly nested) parsed record.
    Nested dict/list values contribute their own keys too, so a record
    with few top-level keys but a nested payload still counts as rich."""
    if isinstance(value, dict):
        return len(value) + sum(_count_fields(v) for v in value.values())
    if isinstance(value, list):
        return sum(_count_fields(v) for v in value)
    return 0


def _passes_quality_filter(
    parsed: object, *, skip_non_dict: bool, minimum_fields: int | None
) -> bool:
    if skip_non_dict and not isinstance(parsed, dict):
        return False
    if minimum_fields is not None and _count_fields(parsed) < minimum_fields:
        return False
    return True


def ingest_dataset(
    dataset_id: DatasetId,
    raw_path: Path,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    parsed_root: Path = DEFAULT_PARSED_ROOT,
    skip_non_dict: bool = True,
    minimum_fields: int | None = 4,
) -> IngestSummary:
    adapter = get_adapter(dataset_id)
    manifest = ManifestStore(manifest_path)
    dataset = ShardedDataset(parsed_root / dataset_id)
    parsed_root.mkdir(parents=True, exist_ok=True)

    files_ingested = 0
    files_skipped = 0
    records_written = 0
    records_dropped = 0

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
                if not _passes_quality_filter(
                    parsed, skip_non_dict=skip_non_dict, minimum_fields=minimum_fields
                ):
                    records_dropped += 1
                    continue
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
        records_dropped=records_dropped,
    )


@click.command()
@click.argument("dataset_id")
@click.argument("path", required=False, default=None, type=click.Path(exists=True, path_type=Path))
def main(dataset_id: str, path: Path | None) -> None:
    """Ingest DATASET_ID's raw files at PATH: extract + parse + manifest + shard."""
    # Checking dataset ID here instead of click.Choice to keep it
    # live across the module's lifetime, same as the registry itself.
    if not adapter_exists(dataset_id):
        raise click.BadParameter(
            f"no adapter registered for dataset_id {dataset_id!r}",
            param_hint="'dataset_id'",
        )

    if path is None:
        path = Path(f"data/raw/{dataset_id}")

    summary = ingest_dataset(dataset_id, path)
    click.echo(
        f"{dataset_id}: ingested {summary.files_ingested} file(s) "
        f"({summary.records_written} records, {summary.records_dropped} dropped by "
        f"quality filter), skipped {summary.files_skipped} already-ingested file(s)"
    )


if __name__ == "__main__":
    main()
