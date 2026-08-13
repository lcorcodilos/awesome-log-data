from __future__ import annotations

import shutil
from pathlib import Path

from awesome_log_data.adapters.evtx_attack_samples import EvtxAttackSamplesAdapter
from awesome_log_data.parsers.evtx_parser import EvtxParser

FIXTURE_EVTX = (
    Path(__file__).parent / "fixtures" / "evtx_attack_samples" / "CA_chrome_firefox_opera_4663.evtx"
)


def _copy_fixture_into(raw_root: Path, relative: str) -> Path:
    dest = raw_root / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_EVTX, dest)
    return dest


def test_discover_finds_nested_evtx_with_no_extraction(tmp_path: Path) -> None:
    _copy_fixture_into(tmp_path, "Discovery/CA_chrome_firefox_opera_4663.evtx")

    sources = list(EvtxAttackSamplesAdapter.discover(tmp_path))

    assert len(sources) == 1
    source = sources[0]
    assert source.path == tmp_path / "Discovery" / "CA_chrome_firefox_opera_4663.evtx"
    assert isinstance(source.parser, EvtxParser)
    assert source.parser.record_ref_type == "event_record_id"
    assert source.license == "GPL-3.0"
    assert source.labeled is True
    assert source.file_name == "Discovery/CA_chrome_firefox_opera_4663.evtx"


def test_discover_extracted_file_parses_to_real_records(tmp_path: Path) -> None:
    _copy_fixture_into(tmp_path, "sample.evtx")

    (source,) = list(EvtxAttackSamplesAdapter.discover(tmp_path))
    records = list(source.parser.parse(source.path))

    assert len(records) == 5
    for ref, record in records:
        assert record["Event"]["System"]["EventRecordID"] == ref


def test_discover_finds_multiple_evtx_files_recursively_and_avoids_basename_collisions(
    tmp_path: Path,
) -> None:
    _copy_fixture_into(tmp_path, "Discovery/sample.evtx")
    _copy_fixture_into(tmp_path, "Persistence/sample.evtx")

    sources = list(EvtxAttackSamplesAdapter.discover(tmp_path))

    assert {s.file_name for s in sources} == {
        "Discovery/sample.evtx",
        "Persistence/sample.evtx",
    }
