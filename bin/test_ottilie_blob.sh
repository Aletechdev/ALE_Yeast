#!/usr/bin/env bash
# Ottilie test, blob edition: same 2 samples (NODRUG-GM2 + CBR110-15-R3a) / 4 chromosomes
# (I, IV, VII, XV) as bin/test_ottilie.sh, but every input is streamed from the PUBLIC
# Azure Blob (no credentials, no SAS, no populated data/ottilie/).
# Uses the ottilie_test_ci profile (conf/test/ottilie_test_ci.config).
# Truth variants: 4 SNVs + chr I whole-chromosome duplication in CBR110-15-R3a
# Source: Ottilie et al., Commun Biol 5:128 (2022)
#
# The one input that CANNOT be a URL is --snpeff_cache: it is a directory param that the
# pipeline validates with isDirectory() and stages as a tree, and Nextflow's http provider
# cannot list a blob prefix. So this script fetches the published snpeff_cache.tar.gz
# (~23 MB) once, untars it locally, and points --snpeff_cache at the untarred dir — the
# fallback DATA_PROVENANCE.md prescribes. FASTQs / FASTA / GenBank / GFF3 / samplesheet are
# single files and stream straight from their URLs.
#
# STORAGE / CLEANUP — streaming does NOT mean "no local copy". Nextflow downloads each remote
# file ONCE per session into <workdir>/stage-<session-uuid>/ and symlinks it into every task dir
# (~366 MB for this test). Two consequences:
#   * `-resume` (passed below) reuses that stage dir. A run WITHOUT -resume gets a new session id
#     → a second full stage-* copy alongside the first. Never drop -resume when reusing the work dir.
#   * `nextflow clean` removes task dirs but NOT stage-* dirs (verified) — so cleaning up means
#     `rm -rf work_ottilie_test_blob` (which also reclaims the staged inputs), not `nextflow clean`.
# The only thing living outside the work dir is the ~23 MB SnpEff cache in .ottilie_ci_cache/.
#
# Usage (from anywhere):
#   bash bin/test_ottilie_blob.sh                    # extra args are passed through to nextflow
# Re-host / new version, or reuse an existing cache:
#   OTTILIE_BLOB_BASE=https://<acct>.blob.core.windows.net/<container>/ottilie/v2 bash bin/test_ottilie_blob.sh
#   OTTILIE_SNPEFF_CACHE=/data/ottilie/S288C_reference_test/snpeff_cache bash bin/test_ottilie_blob.sh
# Force a re-download of the cache:
#   FORCE_CACHE=1 bash bin/test_ottilie_blob.sh

set -euo pipefail

pipeline_folder="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BLOB_BASE="${OTTILIE_BLOB_BASE:-https://aletestdatapublic.blob.core.windows.net/releases/ottilie/v1}"
SNPEFF_CACHE="${OTTILIE_SNPEFF_CACHE:-$pipeline_folder/.ottilie_ci_cache/snpeff_cache}"
SNPEFF_DB="R64-1-1.105"
TARBALL="snpeff_cache.tar.gz"

command -v curl >/dev/null || { echo "ERROR: curl not found." >&2; exit 1; }
command -v tar  >/dev/null || { echo "ERROR: tar not found."  >&2; exit 1; }

# --- Stage the snpeff cache directory (the only non-streamable input) ---
if [[ -d "$SNPEFF_CACHE/$SNPEFF_DB" && -z "${FORCE_CACHE:-}" ]]; then
    echo "SnpEff cache already staged: $SNPEFF_CACHE"
else
    PARENT="$(dirname "$SNPEFF_CACHE")"
    echo "Fetching SnpEff cache from $BLOB_BASE/$TARBALL ..."
    mkdir -p "$PARENT"
    TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
    curl -fSL "$BLOB_BASE/$TARBALL" -o "$TMP/$TARBALL"

    # Best-effort integrity check against the published SHA256SUMS (same contract as download_test_data.sh)
    if curl -fsSL "$BLOB_BASE/SHA256SUMS" -o "$TMP/SHA256SUMS" 2>/dev/null; then
        EXPECTED="$(awk -v f="$TARBALL" '$2==f{print $1}' "$TMP/SHA256SUMS")"
        if [[ -n "$EXPECTED" ]]; then
            ACTUAL="$(sha256sum "$TMP/$TARBALL" | awk '{print $1}')"
            [[ "$EXPECTED" == "$ACTUAL" ]] && echo "  checksum OK" \
                || { echo "ERROR: $TARBALL checksum mismatch (expected $EXPECTED, got $ACTUAL)." >&2; exit 1; }
        fi
    fi

    # The tarball's top-level dir is 'snpeff_cache/', so untar into the PARENT of $SNPEFF_CACHE.
    rm -rf "$SNPEFF_CACHE"
    tar -xzf "$TMP/$TARBALL" -C "$PARENT"
    [[ -d "$SNPEFF_CACHE/$SNPEFF_DB" ]] || {
        echo "ERROR: $TARBALL did not unpack to $SNPEFF_CACHE/$SNPEFF_DB." >&2; exit 1; }
    echo "Staged SnpEff cache: $SNPEFF_CACHE"
fi

# Pin the Nextflow runtime: 25.10.x is the validated line; 26.x can't parse this config.
export NXF_VER=25.10.4
export OTTILIE_BLOB_BASE="$BLOB_BASE"

nextflow run ${pipeline_folder}/main.nf -profile ottilie_test_ci,azureD4as,docker \
    -w ${pipeline_folder}/work_ottilie_test_blob \
    --outdir ${pipeline_folder}/output_ottilie_test_blob \
    --snpeff_cache "$SNPEFF_CACHE" \
    --generate_reports \
    -resume "$@"
