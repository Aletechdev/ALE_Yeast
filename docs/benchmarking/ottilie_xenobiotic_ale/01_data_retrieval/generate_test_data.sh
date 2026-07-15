#!/usr/bin/env bash
# Generate minimal CI/CD test dataset for the ALE Nextflow pipeline.
#
# Extracts reads mapping to chromosomes I, IV, VII, XV from 2 Ottilie pilot
# samples and subsets the S288C reference accordingly.
#
# Provenance:
#   Source:       SRA SRR10985539 (NODRUG-GM2, parent) and SRR10985585 (CBR110-15-R3a, evolved)
#   Publication:  Ottilie et al., Commun Biol 5:128 (2022)
#                 https://doi.org/10.1038/s42003-022-03076-z
#   Chromosomes:  I (chr I dup in CBR110), IV (2 truth SNVs), VII (1 truth SNV), XV (1 truth SNV)
#   Truth SNVs:   IV:205738 C>A (RPO21), IV:1184212 G>T (TRR1),
#                 VII:233903 G>A (ROG1), XV:639861 G>T (YRR1)
#   Truth CNV:    Chr I whole-chromosome duplication (cn=3, log2=0.329) in CBR110-15-R3a
#
# Two modes:
#   --from-cram   (default) Extract from existing pilot CRAM files (fast, requires prior pilot run)
#   --from-sra    Full reproducible path: download from SRA → align → extract (slower)
#
# Prerequisites:
#   conda activate nf-env     (samtools, bwa-mem2, gatk4)
#   conda activate ottilie-benchmark  (sra-tools=3.2.1, only for --from-sra mode)
#
# Usage:
#   cd <repo_root>
#   bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/generate_test_data.sh
#   bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/generate_test_data.sh --from-sra

set -euo pipefail

# ---------- Configuration ----------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Source data
FULL_REF="$REPO_ROOT/data/ottilie/S288C_reference/S288C_R64.fa"
FULL_GB="$REPO_ROOT/data/ottilie/S288C_reference/S288C_R64_ensembl_chrnames.gb"
FULL_CHR_DIR="$REPO_ROOT/data/ottilie/S288C_reference/chromosomes"
FULL_SNPEFF="$REPO_ROOT/data/ottilie/S288C_reference/snpeff_cache"
CRAM_DIR="$REPO_ROOT/output_ottilie/preprocessing/markduplicates"
FASTQ_DIR="$REPO_ROOT/data/ottilie/fastq"

# Output directories
OUT_FASTQ="$REPO_ROOT/data/ottilie/fastq_test"   # chr-subset test FASTQs → referenced by samplesheet (pipeline input)
OUT_REF="$REPO_ROOT/data/ottilie/S288C_reference_test"

# Target chromosomes and samples
CHROMS=("I" "IV" "VII" "XV")
CHROM_REGIONS="I IV VII XV"

declare -A SAMPLES
SAMPLES[NODRUG-GM2]="SRR10985539"
SAMPLES[CBR110-15-R3a]="SRR10985585"

# Parse mode
MODE="from-cram"
if [[ "${1:-}" == "--from-sra" ]]; then
    MODE="from-sra"
fi

echo "============================================"
echo "Generate ALE Test Dataset"
echo "Mode: $MODE"
echo "Chromosomes: ${CHROMS[*]}"
echo "Samples: ${!SAMPLES[*]}"
echo "Output FASTQ: $OUT_FASTQ"
echo "Output Reference: $OUT_REF"
echo "============================================"
echo ""

# ---------- Step 1: Subset reference ----------

echo "=== Step 1: Subset reference ==="
mkdir -p "$OUT_REF/chromosomes"

# 1a. Subset FASTA
echo "  Extracting chromosomes from FASTA..."
samtools faidx "$FULL_REF" $CHROM_REGIONS > "$OUT_REF/S288C_R64_test.fa"
samtools faidx "$OUT_REF/S288C_R64_test.fa"
echo "  FASTA: $(wc -l < "$OUT_REF/S288C_R64_test.fa.fai") contigs"

# 1b. Sequence dictionary (samtools dict — GATK runs in Docker, not in conda)
echo "  Creating sequence dictionary..."
samtools dict "$OUT_REF/S288C_R64_test.fa" > "$OUT_REF/S288C_R64_test.dict"
echo "  Dict created."

# 1c. Copy individual chromosome FASTAs
echo "  Copying chromosome FASTAs..."
for chr in "${CHROMS[@]}"; do
    cp "$FULL_CHR_DIR/${chr}.fa" "$OUT_REF/chromosomes/"
done
echo "  Copied ${#CHROMS[@]} chromosome files."

# 1d. Extract GenBank entries for target chromosomes
#     GenBank records end with '//' on its own line. The file also contains
#     URLs with '//' (e.g. http://...) so we split on '^//$' not just '//'.
echo "  Extracting GenBank entries..."
python3 -c "
import re, sys

target_chroms = set(sys.argv[1:])
gb_path = '$FULL_GB'
out_path = '$OUT_REF/S288C_R64_test.gb'

with open(gb_path) as f:
    content = f.read()

# Split on '//' that appears alone on a line (the GenBank record terminator)
records = re.split(r'\n//\n', content)
kept = []
for rec in records:
    rec_stripped = rec.strip()
    if not rec_stripped:
        continue
    # Only consider records starting with LOCUS
    if not rec_stripped.startswith('LOCUS'):
        continue
    locus_name = rec_stripped.split()[1]
    if locus_name in target_chroms:
        kept.append(rec.rstrip())

with open(out_path, 'w') as f:
    for rec in kept:
        f.write(rec)
        f.write('\n//\n')

names = [r.strip().split(chr(10))[0].split()[1] for r in kept]
print(f'  Extracted {len(kept)} GenBank entries: {names}')
" "${CHROMS[@]}"

# 1e. Copy full SnpEff cache
echo "  Copying SnpEff cache..."
mkdir -p "$OUT_REF/snpeff_cache"
cp -r "$FULL_SNPEFF/R64-1-1.105" "$OUT_REF/snpeff_cache/"
# Copy parent snpEff.config if it exists
if [[ -f "$FULL_SNPEFF/snpEff.config" ]]; then
    cp "$FULL_SNPEFF/snpEff.config" "$OUT_REF/snpeff_cache/"
fi
echo "  SnpEff cache copied."

echo ""

# ---------- Step 2: Extract reads ----------

echo "=== Step 2: Extract reads for target chromosomes ==="
mkdir -p "$OUT_FASTQ"
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

if [[ "$MODE" == "from-cram" ]]; then
    # Extract directly from existing pilot CRAM files
    echo "  Extracting from CRAM files (fast path)..."

    for sample in "${!SAMPLES[@]}"; do
        echo ""
        echo "  --- $sample ---"
        CRAM="$CRAM_DIR/$sample/$sample.md.cram"

        if [[ ! -f "$CRAM" ]]; then
            echo "  ERROR: CRAM not found: $CRAM"
            echo "  Run the pilot pipeline first, or use --from-sra mode."
            exit 1
        fi

        # Extract reads on target chromosomes (paired reads only)
        echo "  Extracting mapped reads on ${CHROMS[*]}..."
        samtools view -b -h \
            --reference "$FULL_REF" \
            -f 1 -F 12 \
            "$CRAM" $CHROM_REGIONS \
            > "$TMPDIR/${sample}.region.bam"

        # Sort by read name for FASTQ extraction
        echo "  Sorting by name..."
        samtools sort -n -@ 2 \
            "$TMPDIR/${sample}.region.bam" \
            -o "$TMPDIR/${sample}.namesort.bam"

        # Convert to paired FASTQ
        echo "  Converting to FASTQ..."
        samtools fastq -@ 2 \
            -1 "$OUT_FASTQ/${sample}_chrI_IV_VII_XV_R1.fastq.gz" \
            -2 "$OUT_FASTQ/${sample}_chrI_IV_VII_XV_R2.fastq.gz" \
            -0 /dev/null -s /dev/null \
            "$TMPDIR/${sample}.namesort.bam"

        # Clean intermediate files
        rm -f "$TMPDIR/${sample}.region.bam" "$TMPDIR/${sample}.namesort.bam"

        # Report
        ls -lh "$OUT_FASTQ/${sample}_chrI_IV_VII_XV_R"*.fastq.gz
    done

elif [[ "$MODE" == "from-sra" ]]; then
    # Full reproducible path: SRA download → align → extract
    echo "  Full SRA-to-FASTQ extraction path..."
    echo ""

    # Check for bwa-mem2
    if ! command -v bwa-mem2 &> /dev/null; then
        echo "  ERROR: bwa-mem2 not found. conda activate nf-env"
        exit 1
    fi

    # Build bwa-mem2 index if needed
    if [[ ! -f "${FULL_REF}.0123" ]]; then
        echo "  Building bwa-mem2 index (one-time, ~30s for yeast)..."
        bwa-mem2 index "$FULL_REF"
    fi

    for sample in "${!SAMPLES[@]}"; do
        SRR="${SAMPLES[$sample]}"
        echo ""
        echo "  --- $sample ($SRR) ---"

        # Check if FASTQs already exist from prior download
        R1="$FASTQ_DIR/${SRR}_1.fastq.gz"
        R2="$FASTQ_DIR/${SRR}_2.fastq.gz"

        if [[ -f "$R1" && -f "$R2" ]]; then
            echo "  Reusing existing FASTQs: $R1"
        else
            echo "  Downloading from SRA..."
            echo "  NOTE: Requires ottilie-benchmark conda env (sra-tools=3.2.1)"
            echo "        Run: conda activate ottilie-benchmark"

            if ! command -v fasterq-dump &> /dev/null; then
                echo "  ERROR: fasterq-dump not found."
                echo "  Install: conda create -n ottilie-benchmark -f $SCRIPT_DIR/environment_data_retrieval.yml"
                exit 1
            fi

            fasterq-dump "$SRR" --split-files --outdir "$TMPDIR" --threads 4
            gzip -f "$TMPDIR/${SRR}_1.fastq"
            gzip -f "$TMPDIR/${SRR}_2.fastq"
            R1="$TMPDIR/${SRR}_1.fastq.gz"
            R2="$TMPDIR/${SRR}_2.fastq.gz"
        fi

        # Align to full reference
        echo "  Aligning to S288C R64..."
        bwa-mem2 mem -t 4 \
            -R "@RG\\tID:${SRR}\\tSM:${sample}\\tPL:ILLUMINA\\tLB:${SRR}" \
            "$FULL_REF" "$R1" "$R2" \
            2>/dev/null \
            | samtools sort -@ 2 -o "$TMPDIR/${sample}.sorted.bam"
        samtools index "$TMPDIR/${sample}.sorted.bam"

        # Extract reads on target chromosomes
        echo "  Extracting reads on ${CHROMS[*]}..."
        samtools view -b -h \
            -f 1 -F 12 \
            "$TMPDIR/${sample}.sorted.bam" $CHROM_REGIONS \
            > "$TMPDIR/${sample}.region.bam"

        # Sort by name and convert to FASTQ
        echo "  Converting to FASTQ..."
        samtools sort -n -@ 2 \
            "$TMPDIR/${sample}.region.bam" \
            -o "$TMPDIR/${sample}.namesort.bam"

        samtools fastq -@ 2 \
            -1 "$OUT_FASTQ/${sample}_chrI_IV_VII_XV_R1.fastq.gz" \
            -2 "$OUT_FASTQ/${sample}_chrI_IV_VII_XV_R2.fastq.gz" \
            -0 /dev/null -s /dev/null \
            "$TMPDIR/${sample}.namesort.bam"

        # Clean intermediate files
        rm -f "$TMPDIR/${sample}"*.bam "$TMPDIR/${sample}"*.bam.bai

        # Report
        ls -lh "$OUT_FASTQ/${sample}_chrI_IV_VII_XV_R"*.fastq.gz
    done
fi

echo ""

# ---------- Step 3: Summary ----------

echo "============================================"
echo "Test data generation complete"
echo "============================================"
echo ""
echo "FASTQ files:"
ls -lh "$OUT_FASTQ/"*.fastq.gz
echo ""
echo "Reference files:"
ls -lh "$OUT_REF/S288C_R64_test.fa" "$OUT_REF/S288C_R64_test.fa.fai" "$OUT_REF/S288C_R64_test.dict"
echo ""
echo "GenBank:"
ls -lh "$OUT_REF/S288C_R64_test.gb"
echo ""
echo "SnpEff cache:"
du -sh "$OUT_REF/snpeff_cache/"
echo ""

echo "MD5 checksums (for verification):"
md5sum "$OUT_FASTQ/"*.fastq.gz
md5sum "$OUT_REF/S288C_R64_test.fa" "$OUT_REF/S288C_R64_test.gb"
echo ""

echo "Read counts:"
for fq in "$OUT_FASTQ/"*.fastq.gz; do
    reads=$(echo $(zcat "$fq" | wc -l) / 4 | bc)
    echo "  $(basename $fq): $reads reads"
done
echo ""

# Write the ottilie test samplesheet with portable, machine-correct absolute paths.
# fastq_1/fastq_2 derive from $OUT_FASTQ (== $REPO_ROOT/data/ottilie/fastq_test), which is
# computed from THIS script's location — so regenerating on any machine (e.g. a new deploy)
# produces a samplesheet valid for that machine, with no hardcoded /home/<user>/... paths.
# Absolute (not relative) so it resolves regardless of launch dir, including nf-test's workdir.
# NOTE: local-FS paths only. For Seqera Cloud / GitHub Actions, generate a separate samplesheet
# with Azure Blob URL paths (see the CI/cloud portability task).
SAMPLESHEET="$REPO_ROOT/data/ottilie/samplesheet_test.csv"
cat > "$SAMPLESHEET" <<CSV
experiment,sample,status,clonal_or_population,ploidy,sex,lane,fastq_1,fastq_2
Ottilie_test,NODRUG-GM2,0,clonal,1,XX,L001,$OUT_FASTQ/NODRUG-GM2_chrI_IV_VII_XV_R1.fastq.gz,$OUT_FASTQ/NODRUG-GM2_chrI_IV_VII_XV_R2.fastq.gz
Ottilie_test,CBR110-15-R3a,0,clonal,1,XX,L001,$OUT_FASTQ/CBR110-15-R3a_chrI_IV_VII_XV_R1.fastq.gz,$OUT_FASTQ/CBR110-15-R3a_chrI_IV_VII_XV_R2.fastq.gz
CSV
echo "Wrote samplesheet: $SAMPLESHEET"
echo ""

echo "Next steps:"
echo "  Run pipeline (from repo root):  nextflow run main.nf -profile ottilie_test,docker"
echo "============================================"
