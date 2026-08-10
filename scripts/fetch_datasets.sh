#!/usr/bin/env bash
# Fetches raw dataset files into data/raw/<dataset_id>/
#
# Usage:
#   scripts/fetch_datasets.sh <dataset_id>   # fetch one dataset
#   scripts/fetch_datasets.sh all            # fetch every non-gated dataset,
#                                             # and print instructions for
#                                             # the gated ones
#   scripts/fetch_datasets.sh list           # list dataset_ids and their
#                                             # gated/direct status
#
# Requires: git, curl. ait_lds also requires jq (Zenodo API file listing).
#
# Gated datasets (LANL family) need a manual form + email-approval step —
# this script prints where to go and what to do, then stops. cert_insider
# (Kilthub/Figshare) isn't login-gated, but doesn't expose a predictable
# per-file download URL from its landing page either, so it gets the same
# print-and-stop treatment for now.

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

print_wall_instructions() {
    local dataset_id="$1"
    local url="$2"
    shift 2
    log "${dataset_id}: gated — manual access required"
    echo ""
    echo "  ${dataset_id} requires a manual step before it can be fetched:"
    echo "    1. Visit ${url}"
    for line in "$@"; do
        echo "    ${line}"
    done
    echo "    Place the downloaded files under data/raw/${dataset_id}/"
    echo ""
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

# --- gated: LANL family -------------------------------------------------

fetch_lanl_uhnd() {
    print_wall_instructions lanl_uhnd "https://csr.lanl.gov/data/2017/" \
        "2. Submit your email + use case in the access request form —" \
        "   download links are granted immediately, no approval wait." \
        "3. Recommended to only download 7-8 CONSECUTIVE days of wls (host) .gz files —" \
        "   not all ~60. Each is ~400MB compressed -> ~12GB uncompressed," \
        "   so the full set is impractically large for what's needed" \
        "   here. " \
        "   Skip netflow entirely — huge, and not expected to add much" \
        "   over LANL Comprehensive's flows.txt.gz."
}

fetch_lanl_comprehensive() {
    print_wall_instructions lanl_comprehensive "https://csr.lanl.gov/data/cyber1/" \
        "2. Submit your email + use case in the access request form —" \
        "   download links are granted immediately, no approval wait." \
        "3. Download auth.txt.gz, proc.txt.gz, flows.txt.gz, dns.txt.gz," \
        "   redteam.txt.gz."
}

# --- gated (soft): cert_insider ------------------------------------------

fetch_cert_insider() {
    print_wall_instructions cert_insider \
        "https://kilthub.cmu.edu/articles/dataset/Insider_Threat_Test_Dataset/12841247" \
        "2. Select release r6.2 in the version dropdown (or the latest release)." \
        "3. Download the files from that release (no login required, but" \
        "   there's no stable direct-download URL to script against)."
}

# --- dispatch -------------------------------------------------------------

DIRECT_DATASETS=(otrf evtx_attack_samples flaws_cloud ait_lds elastic_fixtures)
GATED_DATASETS=(lanl_uhnd lanl_comprehensive cert_insider)
ALL_DATASETS=("${DIRECT_DATASETS[@]}" "${GATED_DATASETS[@]}")

usage() {
    echo "Usage: $0 <dataset_id|all|list>"
    echo ""
    echo "Direct (fetchable now):"
    printf '  %s\n' "${DIRECT_DATASETS[@]}"
    echo "Gated (prints manual-access instructions):"
    printf '  %s\n' "${GATED_DATASETS[@]}"
}

list_datasets() {
    echo "direct:"
    printf '  %s\n' "${DIRECT_DATASETS[@]}"
    echo "gated:"
    printf '  %s\n' "${GATED_DATASETS[@]}"
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
        otrf|evtx_attack_samples|flaws_cloud|ait_lds|elastic_fixtures|\
        lanl_uhnd|lanl_comprehensive|cert_insider)
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
