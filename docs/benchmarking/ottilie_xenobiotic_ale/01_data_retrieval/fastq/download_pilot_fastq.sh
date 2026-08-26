#!/usr/bin/env bash
# Download the 4-sample full-depth ottilie PILOT set from SRA and write its samplesheet.
#
# Self-contained: runs from inside the repo OR from an extracted ottilie_test_data.tar.gz bundle
# (it ships there so anyone can pull the pilot reads without the repo). Needs only sra-tools
# (fasterq-dump) and gzip.
#
# Prerequisites:
#   conda activate ottilie-benchmark        # repo env, environment_data_retrieval.yml
#   # or standalone:
#   conda create -n sra -c bioconda -c conda-forge sra-tools=3.2.1 && conda activate sra
#   # sra-tools 3.2.1 — do NOT use 3.4.1, it segfaults
#
# Usage:
#   bash download_pilot_fastq.sh                      # inside the repo → data/ottilie/fastq/
#   OUT=/scratch/ottilie bash download_pilot_fastq.sh  # anywhere → $OUT/fastq/ + $OUT/samplesheet_pilot.csv
#
# Samples (pipeline name — Sup Data 4 spelling — SRA run — published truth events):
#   NODRUG-GM2         NODRUG--GM2          SRR10985539  parent: ABC16-Green Monster, no drug, no truth events
#   Doxorubicin16-R2b  Doxorubicin-16--R2b  SRR10985527  EAW304  2 SNVs + 21 INDELs (PMS1 K724* mutator)
#   Carmaphycin-R9-2   Carmaphycin--R9-2    SRR10985678  EAW131  15 SNVs
#   CBR110-15-R3a      CBR110-15R3a         SRR10985585  EAW744  4 SNVs + chr I whole-chromosome duplication
# Truth set per event: pilot_truth_set.csv (Sup Data 4 + 5). Name reconciliation across the paper's
# tables and SRA: sample_name_dictionary.csv. Both ship beside this script in the bundle and live in
# data/ottilie/ in the repo.
#
# Output files keep their SRA names (SRR<run>_{1,2}.fastq.gz); the samplesheet is what maps them
# to sample names, so it is written here rather than left for the user to assemble.
#
# Expected: ~2.7 GB compressed SRA → ~5-6 GB uncompressed FASTQ → ~2 GB gzipped
# Runtime:  ~2-5 min per sample depending on network speed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Inside the repo the script sits 5 levels below the root and data/ottilie/ is the convention;
# anywhere else (an extracted bundle) fall back to the script's own directory unless OUT is set.
if [[ -z "${OUT:-}" ]]; then
    candidate="$(cd "$SCRIPT_DIR/../../../../.." 2>/dev/null && pwd || true)"
    if [[ -n "$candidate" && -f "$candidate/main.nf" && -d "$candidate/docs/benchmarking" ]]; then
        OUT="$candidate/data/ottilie"
    else
        OUT="$SCRIPT_DIR"
    fi
fi
FASTQ_DIR="$OUT/fastq"
SAMPLESHEET="$OUT/samplesheet_pilot.csv"
mkdir -p "$FASTQ_DIR"

command -v fasterq-dump >/dev/null || { echo "ERROR: fasterq-dump not found — install sra-tools 3.2.1 (see header)." >&2; exit 1; }

# sample:SRA run — parent first, then evolved (deterministic order; same pairs as upload_pilot_data.sh)
PAIRS=(
    NODRUG-GM2:SRR10985539
    Doxorubicin16-R2b:SRR10985527
    Carmaphycin-R9-2:SRR10985678
    CBR110-15-R3a:SRR10985585
)
TOTAL=${#PAIRS[@]}

echo "FASTQ directory: $FASTQ_DIR"
for i in "${!PAIRS[@]}"; do
    SAMPLE="${PAIRS[$i]%%:*}"; SRR="${PAIRS[$i]##*:}"
    NUM=$((i + 1))
    echo "============================================"
    echo "[$NUM/$TOTAL] $SAMPLE ($SRR)"
    echo "============================================"

    if [[ -f "$FASTQ_DIR/${SRR}_1.fastq.gz" && -f "$FASTQ_DIR/${SRR}_2.fastq.gz" ]]; then
        echo "  Already exists, skipping."
        continue
    fi

    # Clean up any partial files from previous attempts
    rm -f "$FASTQ_DIR/${SRR}_1.fastq" "$FASTQ_DIR/${SRR}_2.fastq" \
          "$FASTQ_DIR/${SRR}_1.fastq.gz" "$FASTQ_DIR/${SRR}_2.fastq.gz"
    rm -rf "$FASTQ_DIR/fasterq.tmp."*

    echo "  Downloading and converting to FASTQ..."
    fasterq-dump "$SRR" --split-files --outdir "$FASTQ_DIR" --threads 4

    if [[ ! -f "$FASTQ_DIR/${SRR}_1.fastq" || ! -f "$FASTQ_DIR/${SRR}_2.fastq" ]]; then
        echo "  ERROR: Expected paired-end files not found after fasterq-dump" >&2
        ls -la "$FASTQ_DIR/${SRR}"* 2>/dev/null || true
        exit 1
    fi

    # Compress sequentially (parallel gzip causes issues in some shell contexts)
    echo "  Compressing R1..."; gzip -f "$FASTQ_DIR/${SRR}_1.fastq"
    echo "  Compressing R2..."; gzip -f "$FASTQ_DIR/${SRR}_2.fastq"
    echo "  Done:"; ls -lh "$FASTQ_DIR/${SRR}_1.fastq.gz" "$FASTQ_DIR/${SRR}_2.fastq.gz"
    echo ""
done

# Samplesheet with absolute paths for THIS machine — regenerate here, never copy between machines.
# All samples are haploid, clonal, untreated (status 0): joint-germline calling, no tumor/normal.
{
    echo "experiment,sample,status,clonal_or_population,ploidy,sex,lane,fastq_1,fastq_2"
    for pair in "${PAIRS[@]}"; do
        SAMPLE="${pair%%:*}"; SRR="${pair##*:}"
        echo "Ottilie_pilot,$SAMPLE,0,clonal,1,XX,L001,$FASTQ_DIR/${SRR}_1.fastq.gz,$FASTQ_DIR/${SRR}_2.fastq.gz"
    done
} > "$SAMPLESHEET"

echo "============================================"
echo "All $TOTAL pilot samples present in $FASTQ_DIR"
ls -lh "$FASTQ_DIR"/SRR109855{39,27}_*.fastq.gz "$FASTQ_DIR"/SRR109856{78,85}_*.fastq.gz 2>/dev/null || ls -lh "$FASTQ_DIR"/*.fastq.gz
echo "Wrote samplesheet: $SAMPLESHEET"
echo ""
echo "Pair these reads with the FULL reference (S288C_reference/, all 16 chromosomes + Mito) — never"
echo "the 4-chromosome S288C_reference_test/. See README.md in the bundle."
echo "============================================"
