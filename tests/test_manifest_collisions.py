"""Tests for compute_source_id's collision handling (PLAN.md Section 2) —
the AIT-LDS case where the same file_name (e.g. access.log) is genuinely
reused across multiple hosts within one dataset.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from awesome_log_data.manifest import (
    ManifestEntry,
    ManifestStore,
    compute_source_id,
    sha256_file,
)


def _entry(source_id: str, file_name: str, checksum: str) -> ManifestEntry:
    return ManifestEntry(
        source_id=source_id,
        dataset_id="ait_lds",
        file_name=file_name,
        source_url="https://example.com",
        license="CC-BY-4.0",
        ingested_at="2026-08-09",
        checksum_sha256=checksum,
        bytes=100,
        record_count=5,
        labeled=True,
        record_ref_type="byte_offset",
        notes="",
    )


def test_compute_source_id_returns_base_candidate_when_unseen(tmp_path: Path) -> None:
    store = ManifestStore(tmp_path / "manifest.jsonl")
    file_path = tmp_path / "access.log"
    file_path.write_bytes(b"log line one\n")

    source_id = compute_source_id("ait_lds", "host_a/logs/apache/access.log", file_path, store)

    assert source_id == "ait_lds/host_a/logs/apache/access.log"


def test_compute_source_id_is_idempotent_for_same_file(tmp_path: Path) -> None:
    file_path = tmp_path / "access.log"
    file_path.write_bytes(b"log line one\n")
    checksum = sha256_file(file_path)

    store = ManifestStore(tmp_path / "manifest.jsonl")
    store.upsert(_entry("ait_lds/access.log", "access.log", checksum))

    source_id = compute_source_id("ait_lds", "access.log", file_path, store)

    assert source_id == "ait_lds/access.log"


def test_compute_source_id_disambiguates_genuine_collision(tmp_path: Path) -> None:
    existing_path = tmp_path / "existing.log"
    existing_path.write_bytes(b"host A content\n")
    existing_checksum = sha256_file(existing_path)

    store = ManifestStore(tmp_path / "manifest.jsonl")
    store.upsert(_entry("ait_lds/access.log", "access.log", existing_checksum))

    new_path = tmp_path / "new.log"
    new_path.write_bytes(b"host B content, different bytes\n")
    new_checksum = sha256_file(new_path)

    source_id = compute_source_id("ait_lds", "access.log", new_path, store)

    assert source_id == f"ait_lds/access.log#{new_checksum[:8]}"


def test_compute_source_id_collision_disambiguation_is_deterministic(
    tmp_path: Path,
) -> None:
    existing_path = tmp_path / "existing.log"
    existing_path.write_bytes(b"host A content\n")
    existing_checksum = sha256_file(existing_path)

    store = ManifestStore(tmp_path / "manifest.jsonl")
    store.upsert(_entry("ait_lds/access.log", "access.log", existing_checksum))

    new_path = tmp_path / "new.log"
    new_path.write_bytes(b"host B content, different bytes\n")

    first = compute_source_id("ait_lds", "access.log", new_path, store)
    second = compute_source_id("ait_lds", "access.log", new_path, store)

    assert first == second


def test_compute_source_id_logs_yellow_warning_on_genuine_collision(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    existing_path = tmp_path / "existing.log"
    existing_path.write_bytes(b"host A content\n")
    existing_checksum = sha256_file(existing_path)

    store = ManifestStore(tmp_path / "manifest.jsonl")
    store.upsert(_entry("ait_lds/access.log", "access.log", existing_checksum))

    new_path = tmp_path / "new.log"
    new_path.write_bytes(b"host B content, different bytes\n")

    with caplog.at_level(logging.WARNING, logger="awesome_log_data.manifest"):
        source_id = compute_source_id("ait_lds", "access.log", new_path, store)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "WARNING"
    message = record.getMessage()
    assert "\x1b[33m" in message  # ANSI yellow
    assert "\x1b[0m" in message  # ANSI reset
    assert source_id in message


def test_compute_source_id_does_not_log_when_no_collision(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = ManifestStore(tmp_path / "manifest.jsonl")
    file_path = tmp_path / "access.log"
    file_path.write_bytes(b"log line one\n")

    with caplog.at_level(logging.WARNING, logger="awesome_log_data.manifest"):
        compute_source_id("ait_lds", "access.log", file_path, store)

    assert caplog.records == []
