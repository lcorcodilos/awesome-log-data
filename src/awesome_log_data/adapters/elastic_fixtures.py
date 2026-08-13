"""Elastic `integrations` repo test fixtures adapter.

Raw input is a sparse checkout of
packages/*/data_stream/*/_dev/test/pipeline/, containing hundreds of
heterogeneous vendor log formats used to test Elastic's own ingest
pipelines. Scoped to just the JSON-native ones — the same
structured-content bar applied throughout this project — via two source
shapes, both confirmed against real files in this directory:

1. **`test-*.log`** — NDJSON, one JSON object per line (confirmed e.g.
   Okta, AWS CloudTrail). Qualifies if every non-blank line is valid JSON;
   `JsonLinesParser`.
2. **`test-*.json`** — the `{"events": [...]}` test-harness wrapper format
   (confirmed e.g. auth0, o365, zoom, carbonblack_edr). Each event is
   normalized (see `elastic_events_parser.py`) and the file qualifies if
   at least one event normalizes to a usable record; `ElasticEventsParser`.

Excluded, all confirmed against real files here:

- `*-expected.json` — ECS-mapped pipeline *output*, not raw source data
  (excluded from both the `.log` and `.json` glob by construction, since
  `test-*.json` matches `test-*-expected.json` — handled explicitly).
- `*-config.yml` — pipeline test harness config, not a log.
- `test-*.log` files whose content isn't JSON — hundreds of
  vendor-specific text/syslog/CEF formats (confirmed e.g. bluecoat). Out
  of scope: would need a Grok pattern per vendor for no clear benefit over
  the JSON-native packages already covered.
- `test-*.json` files whose events are all unnormalizable — e.g.
  citrix_adc wraps plain syslog text (not JSON) in `{"message": ...}`.

Which files qualify is determined by probing content, not a hardcoded
package whitelist — this naturally picks up whatever JSON-native packages
are present in the checkout.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from awesome_log_data.adapters import register
from awesome_log_data.base import DatasetId, SourceFile
from awesome_log_data.parsers.elastic_events_parser import ElasticEventsParser, normalize_event
from awesome_log_data.parsers.json_lines_parser import JsonLinesParser, is_json_lines

_LOG_GLOB = "packages/*/data_stream/*/_dev/test/pipeline/test-*.log"
_JSON_GLOB = "packages/*/data_stream/*/_dev/test/pipeline/test-*.json"


def _has_any_normalizable_event(path: Path) -> bool:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        return False
    return any(normalize_event(event) is not None for event in data["events"])


@register
class ElasticFixturesAdapter:
    dataset_id: ClassVar[DatasetId] = "elastic_fixtures"
    source_url: ClassVar[str] = "https://github.com/elastic/integrations"
    license: ClassVar[str] = "Elastic-2.0"

    @staticmethod
    def discover(root: Path) -> Iterator[SourceFile]:
        lines_parser = JsonLinesParser()
        for log_path in sorted(root.glob(_LOG_GLOB)):
            if not is_json_lines(log_path):
                continue
            yield SourceFile(
                file_name=log_path.relative_to(root).as_posix(),
                path=log_path,
                parser=lines_parser,
                source_url=ElasticFixturesAdapter.source_url,
                license=ElasticFixturesAdapter.license,
                labeled=False,
            )

        events_parser = ElasticEventsParser()
        for json_path in sorted(root.glob(_JSON_GLOB)):
            if json_path.name.endswith("-expected.json"):
                continue
            if not _has_any_normalizable_event(json_path):
                continue
            yield SourceFile(
                file_name=json_path.relative_to(root).as_posix(),
                path=json_path,
                parser=events_parser,
                source_url=ElasticFixturesAdapter.source_url,
                license=ElasticFixturesAdapter.license,
                labeled=False,
            )
