#!/usr/bin/env bash
# Uploads the ottilie test dataset to the SAME storage account the pipeline runs against,
# so `snpeff_cache` can be tested as an `az://` directory param.
#
# WHY THIS MATTERS
#   snpeff_cache is a *directory* param. The published public copy is served over https,
#   and Nextflow's http provider has no directory listing — so an https prefix cannot be
#   walked or staged, which is why bin/test_ottilie_blob.sh untars a tarball locally first.
#   `az://` is different: nf-azure implements a real java.nio FileSystemProvider, so a
#   prefix *may* be listable. That is the hypothesis under test.
#
#   Caveat already established: this storage account has hierarchical namespace DISABLED
#   (isHnsEnabled = null), so az:// "directories" are virtual prefixes with no directory
#   objects. AzPath.isDirectory() returns false for them. The pipeline already skips the
#   isDirectory() guard for cloud paths (commit 1f03f38), so the guard is not the risk —
#   the risk is `Channel.fromPath(file(...), checkIfExists: true)` in
#   subworkflows/local/annotation_cache_initialisation/main.nf failing on a virtual prefix.
#
#   Fallback if it fails: chr_dir already accepts a .tar.gz and untars it via UNTAR_CHR_DIR
#   (subworkflows/local/prepare_genome/main.nf). snpeff_cache has NO such path — adding one
#   is the durable fix, and it works over any protocol.
#
#   ./08_upload_test_data.sh 2>&1 | tee "logs/08_$(date -u +%Y%m%dT%H%M%SZ).log"

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./00_vars.sh

REPO_ROOT="$(git -C . rev-parse --show-toplevel 2>/dev/null || echo "$PWD/../../..")"
SRC="${SRC:-$REPO_ROOT/data/ottilie}"
CONTAINER="${CONTAINER:-aletest}"
PREFIX="${PREFIX:-ottilie/v1}"
OVERWRITE="${OVERWRITE:-false}"

[[ -d "$SRC" ]] || { echo "FATAL: test data not found at $SRC" >&2; exit 1; }
[[ -d "$SRC/S288C_reference_test/snpeff_cache" ]] || {
    echo "FATAL: $SRC/S288C_reference_test/snpeff_cache missing — nothing to test" >&2; exit 1; }

echo "source     : $SRC"
echo "destination: az://$CONTAINER/$PREFIX  (account $STORAGE_ACCOUNT)"
echo "overwrite  : $OVERWRITE"
echo
echo "Uploading only the TEST subset (~400 MB), not all of data/ottilie (~64 GB):"
du -sh "$SRC/S288C_reference_test" "$SRC/fastq_test" 2>/dev/null
echo
read -r -p "Proceed? [y/N] " reply
[[ "$reply" == "y" || "$reply" == "Y" ]] || { echo "aborted"; exit 1; }

up() {
    local subdir="$1"
    echo
    echo "--- uploading $subdir/"
    az storage blob upload-batch \
        --account-name "$STORAGE_ACCOUNT" --auth-mode login \
        --destination "$CONTAINER" \
        --destination-path "$PREFIX/$subdir" \
        --source "$SRC/$subdir" \
        --overwrite "$OVERWRITE" \
        --output none
    echo "    done"
}

up "S288C_reference_test"
up "fastq_test"

# The mutation-report GFF3 lives in S288C_reference/ (NOT the _test/ subset) and is
# REQUIRED whenever generate_reports is true — which is the pipeline default. Omitting
# it aborts the run with a misleading "sample-sheet only contains tumor-samples" error.
echo
echo "--- uploading the mutation-report GFF3"
az storage blob upload \
    --account-name "$STORAGE_ACCOUNT" --auth-mode login \
    -c "$CONTAINER" -n "$PREFIX/S288C_reference/S288C_R64.gff3" \
    -f "$SRC/S288C_reference/S288C_R64.gff3" --overwrite --output none
echo "    done"

# The samplesheet cannot be uploaded as-is: its fastq_1/fastq_2 columns hold local
# absolute paths, which mean nothing to a Batch node. Rewrite them to az:// first.
echo
echo "--- generating + uploading the az:// samplesheet"
SHEET_TMP="$(mktemp)"; trap 'rm -f "$SHEET_TMP"' EXIT
sed "s|${SRC}/|az://$CONTAINER/$PREFIX/|g" "$SRC/samplesheet_test.csv" > "$SHEET_TMP"
grep -q '^az://\|,az://' "$SHEET_TMP" || {
    echo "FATAL: rewrite produced no az:// paths — check that $SRC matches the paths in samplesheet_test.csv" >&2
    exit 1; }
az storage blob upload \
    --account-name "$STORAGE_ACCOUNT" --auth-mode login \
    -c "$CONTAINER" -n "$PREFIX/samplesheet_test_az.csv" \
    -f "$SHEET_TMP" --overwrite --output none
echo "    done -> az://$CONTAINER/$PREFIX/samplesheet_test_az.csv"

echo
echo "=== verify: blobs under the snpeff_cache prefix ==="
az storage blob list --account-name "$STORAGE_ACCOUNT" --auth-mode login \
    -c "$CONTAINER" --prefix "$PREFIX/S288C_reference_test/snpeff_cache" \
    --query '[].{name:name, bytes:properties.contentLength}' -o table

echo
echo "=== the az:// paths to test with ==="
cat <<EOF
  --snpeff_cache  az://$CONTAINER/$PREFIX/S288C_reference_test/snpeff_cache
  --chr_dir       az://$CONTAINER/$PREFIX/S288C_reference_test/chromosomes
  --fasta         az://$CONTAINER/$PREFIX/S288C_reference_test/S288C_R64_test.fa

The snpeff_cache prefix must contain a '$PREFIX/.../snpeff_cache/R64-1-1.105/' level —
the pipeline looks for \$snpeff_cache/\$snpeff_db, not the cache root alone.
EOF

echo
echo "NOTE: the SP has Storage Blob Data Contributor on $STORAGE_ACCOUNT, so it can read"
echo "      these blobs at run time. No SAS token or shared key is needed."
