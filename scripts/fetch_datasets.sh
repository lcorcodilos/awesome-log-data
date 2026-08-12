#!/usr/bin/env bash
# Fetches raw dataset files into data/raw/<dataset_id>/
#
# Usage:
#   scripts/fetch_datasets.sh <dataset_id>   # fetch one dataset
#   scripts/fetch_datasets.sh all            # fetch every dataset
#   scripts/fetch_datasets.sh list           # list dataset_ids
#
# Requires: git, curl. ait_lds also requires jq (Zenodo API file listing).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="${REPO_ROOT}/data/raw"
LOG_FILE="${RAW_DIR}/fetch.log"

log() {
    mkdir -p "$RAW_DIR"
    local line
    line="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
    echo "$line"
    echo "$line" >> "$LOG_FILE"
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "error: '$1' is required but not found on PATH" >&2
        exit 1
    fi
}

# If the repo uses git-lfs and git-lfs isn't installed,
# a plain `git clone` doesn't error — it silently leaves small pointer
# stub files in place of the real binary content, so this has to fail
# loudly rather than let that pass silently.
check_no_lfs() {
    local dataset_id="$1"
    local repo_dir="$2"
    local attrs
    attrs="$(git -C "$repo_dir" show HEAD:.gitattributes 2>/dev/null || true)"
    if echo "$attrs" | grep -q 'filter=lfs'; then
        echo "error: ${dataset_id} uses git-lfs ('filter=lfs' found in .gitattributes)." >&2
        echo "       Cloned files may be small pointer stubs, not the real binary data." >&2
        echo "       Install git-lfs (https://git-lfs.com), then run:" >&2
        echo "         git -C '${repo_dir}' lfs pull" >&2
        exit 1
    fi
}

# --- otrf ---------------------------------------------------------------

fetch_otrf() {
    require_cmd git
    local out_dir="${RAW_DIR}/otrf"
    log "otrf: cloning OTRF/Security-Datasets (shallow)"
    if [ -d "${out_dir}/.git" ]; then
        log "otrf: already cloned at ${out_dir}, pulling latest"
        git -C "$out_dir" pull --ff-only
    else
        mkdir -p "$out_dir"
        git clone --depth 1 https://github.com/OTRF/Security-Datasets.git "$out_dir"
    fi
    check_no_lfs otrf "$out_dir"
    log "otrf: done"
}

# --- evtx_attack_samples --------------------------------------------------

fetch_evtx_attack_samples() {
    require_cmd git
    local out_dir="${RAW_DIR}/evtx_attack_samples"
    log "evtx_attack_samples: cloning sbousseaden/EVTX-ATTACK-SAMPLES (shallow)"
    if [ -d "${out_dir}/.git" ]; then
        log "evtx_attack_samples: already cloned at ${out_dir}, pulling latest"
        git -C "$out_dir" pull --ff-only
    else
        mkdir -p "$out_dir"
        git clone --depth 1 https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES.git "$out_dir"
    fi
    check_no_lfs evtx_attack_samples "$out_dir"
    log "evtx_attack_samples: done"
}

# --- flaws_cloud ----------------------------------------------------------

fetch_flaws_cloud() {
    require_cmd curl
    local out_dir="${RAW_DIR}/flaws_cloud"
    local url="https://summitroute.com/downloads/flaws_cloudtrail_logs.tar"
    mkdir -p "$out_dir"
    log "flaws_cloud: downloading ${url}"
    curl -fSL -o "${out_dir}/flaws_cloudtrail_logs.tar" "$url"
    log "flaws_cloud: done"
}

# --- ait_lds ----------------------------------------------------------

fetch_ait_lds() {
    require_cmd curl
    require_cmd jq
    local record_id="19483937"
    local out_dir="${RAW_DIR}/ait_lds"
    local api_url="https://zenodo.org/api/records/${record_id}"
    mkdir -p "$out_dir"
    log "ait_lds: listing files for Zenodo record ${record_id}"

    local files_json
    files_json="$(curl -fsSL "$api_url")"

    local filename url
    echo "$files_json" \
        | jq -r '.files[] | select(.key | contains("no-pcaps")) | "\(.key)\t\(.links.self)"' \
        | while IFS=$'\t' read -r filename url; do
            log "ait_lds: downloading ${filename}"
            curl -fSL -o "${out_dir}/${filename}" "$url"
        done
    log "ait_lds: done"
}

# --- elastic_fixtures -------------------------------------------------

fetch_elastic_fixtures() {
    require_cmd git
    local out_dir="${RAW_DIR}/elastic_fixtures"
    local pattern='packages/*/data_stream/*/_dev/test/pipeline/**'
    log "elastic_fixtures: sparse-checkout of elastic/integrations test fixtures"
    if [ -d "${out_dir}/.git" ]; then
        log "elastic_fixtures: already cloned at ${out_dir}, pulling latest"
        git -C "$out_dir" pull --ff-only
    else
        mkdir -p "$out_dir"
        git clone --depth 1 --filter=blob:none --sparse \
            https://github.com/elastic/integrations.git "$out_dir"
    fi
    git -C "$out_dir" sparse-checkout init --no-cone
    git -C "$out_dir" sparse-checkout set --no-cone "$pattern"
    check_no_lfs elastic_fixtures "$out_dir"
    log "elastic_fixtures: done"
}

# --- dispatch -------------------------------------------------------------

ALL_DATASETS=(otrf evtx_attack_samples flaws_cloud ait_lds elastic_fixtures)

usage() {
    echo "Usage: $0 <dataset_id|all|list>"
    echo ""
    echo "Datasets:"
    printf '  %s\n' "${ALL_DATASETS[@]}"
}

list_datasets() {
    printf '%s\n' "${ALL_DATASETS[@]}"
}

main() {
    if [ "$#" -ne 1 ]; then
        usage
        exit 1
    fi

    case "$1" in
        list)
            list_datasets
            ;;
        all)
            for dataset_id in "${ALL_DATASETS[@]}"; do
                "fetch_${dataset_id}"
            done
            ;;
        otrf|evtx_attack_samples|flaws_cloud|ait_lds|elastic_fixtures)
            "fetch_$1"
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "error: unknown dataset_id '$1'" >&2
            usage
            exit 1
            ;;
    esac
}

main "$@"
