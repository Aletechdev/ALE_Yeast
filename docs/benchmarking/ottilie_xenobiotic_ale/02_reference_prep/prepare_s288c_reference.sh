#!/bin/bash
# Prepare S288C R64-1-1 reference genome for Sarek pipeline (Ottilie benchmark)
#
# Downloads and processes:
#   1. FASTA from Ensembl (Roman numeral chr names: I-XVI, Mito)
#   2. GFF3 annotations from Ensembl
#   3. GenBank from NCBI (renamed to Ensembl chr names for breseq)
#   4. Individual chromosome FASTAs for Control-FREEC --chr_dir
#   5. SnpEff cache (built locally, snpeff.blob.core.windows.net unreachable from Azure VM)
#
# Why Ensembl? Chromosome names must match SnpEff R64-1-1.105 database (Roman numerals).
# NCBI uses NC_* accessions which would cause mismatches.
#
# Usage:
#   conda activate nf-env
#   bash bin/benchmarking/ottilie_xenobiotic_ale/prepare_s288c_reference.sh [output_dir]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${1:-data/ottilie/S288C_reference}"

mkdir -p "${OUTPUT_DIR}"
cd "${OUTPUT_DIR}"

echo "=== 1/5: Downloading FASTA from Ensembl release 105 ==="
if [ ! -f S288C_R64.fa ]; then
    wget -q "https://ftp.ensembl.org/pub/release-105/fasta/saccharomyces_cerevisiae/dna/Saccharomyces_cerevisiae.R64-1-1.dna.toplevel.fa.gz" \
        -O S288C_R64.fa.gz
    gunzip S288C_R64.fa.gz
    samtools faidx S288C_R64.fa
    echo "  Downloaded and indexed S288C_R64.fa"
else
    echo "  S288C_R64.fa already exists, skipping"
fi

echo "=== 2/5: Downloading GFF3 annotations from Ensembl release 105 ==="
if [ ! -f S288C_R64.gff3 ]; then
    wget -q "https://ftp.ensembl.org/pub/release-105/gff3/saccharomyces_cerevisiae/Saccharomyces_cerevisiae.R64-1-1.105.gff3.gz" \
        -O S288C_R64.gff3.gz
    gunzip S288C_R64.gff3.gz
    echo "  Downloaded S288C_R64.gff3 ($(wc -l < S288C_R64.gff3) lines)"
else
    echo "  S288C_R64.gff3 already exists, skipping"
fi

echo "=== 3/5: Downloading GenBank from NCBI and renaming chromosomes ==="
if [ ! -f S288C_R64_ensembl_chrnames.gb ]; then
    # Download original NCBI GenBank (NC_* accession chr names, embedded sequences)
    wget -q "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/146/045/GCF_000146045.2_R64/GCF_000146045.2_R64_genomic.gbff.gz" \
        -O S288C_R64.gbff.gz
    gunzip S288C_R64.gbff.gz
    echo "  Downloaded S288C_R64.gbff (NCBI original)"

    # Rename NC_* accessions to Ensembl Roman numerals
    bash "${SCRIPT_DIR}/rename_genbank_chromosomes.sh" S288C_R64.gbff S288C_R64_ensembl_chrnames.gb
    echo "  Created S288C_R64_ensembl_chrnames.gb (Ensembl chr names)"
else
    echo "  S288C_R64_ensembl_chrnames.gb already exists, skipping"
fi

echo "=== 4/5: Splitting FASTA into individual chromosomes for Control-FREEC ==="
if [ ! -d chromosomes ] || [ "$(ls chromosomes/*.fa 2>/dev/null | wc -l)" -lt 17 ]; then
    mkdir -p chromosomes
    while read chr; do
        samtools faidx S288C_R64.fa "$chr" > "chromosomes/${chr}.fa"
    done < <(grep "^>" S288C_R64.fa | sed 's/^>//' | cut -d' ' -f1)
    echo "  Created $(ls chromosomes/*.fa | wc -l) chromosome files in chromosomes/"
else
    echo "  chromosomes/ already populated, skipping"
fi

echo "=== 5/5: Building SnpEff cache (R64-1-1.105) ==="
DB_NAME="R64-1-1.105"
if [ ! -f "snpeff_cache/${DB_NAME}/snpEffectPredictor.bin" ]; then
    mkdir -p "snpeff_cache/${DB_NAME}"

    # snpEff config
    cat > "snpeff_cache/snpEff.config" <<EOF
data.dir = $(pwd)/snpeff_cache
${DB_NAME}.genome : Saccharomyces_cerevisiae
EOF
    cat > "snpeff_cache/${DB_NAME}/snpEff.config" <<EOF
${DB_NAME}.genome : Saccharomyces_cerevisiae
EOF

    # Copy inputs for snpEff build
    # Fix Ensembl GFF3 for SnpEff 5.1 compatibility:
    # 1. Strip type prefixes from ID/Parent (gene:, transcript:, CDS:, chromosome:)
    #    — SnpEff can't resolve the gene→mRNA→CDS hierarchy with prefixed IDs,
    #    causing WARNING_TRANSCRIPT_NO_START_CODON and broken gene models
    # 2. Strip exon Name= and exon_id= attributes — SnpEff treats these as
    #    independent gene models (e.g. YAR050W_mRNA-E1 instead of FLO1)
    sed '
      /\texon\t/s/;Name=[^;]*//
      /\texon\t/s/;exon_id=[^;]*//
      s/ID=gene:/ID=/g
      s/ID=transcript:/ID=/g
      s/ID=CDS:/ID=/g
      s/ID=chromosome:/ID=/g
      s/Parent=gene:/Parent=/g
      s/Parent=transcript:/Parent=/g
    ' S288C_R64.gff3 > "snpeff_cache/${DB_NAME}/genes.gff"
    cp S288C_R64.fa   "snpeff_cache/${DB_NAME}/sequences.fa"

    # Build database inside Docker container
    # -noCheckCds -noCheckProtein: skip validation (no CDS/protein FASTA available)
    docker run --rm \
        -v "$(pwd)/snpeff_cache:/data/cache" \
        quay.io/biocontainers/snpeff:5.1--hdfd78af_2 \
        snpEff build -gff3 -noCheckCds -noCheckProtein \
            -dataDir /data/cache \
            -c /data/cache/snpEff.config \
            ${DB_NAME} 2>&1 | tail -3

    if [ -f "snpeff_cache/${DB_NAME}/snpEffectPredictor.bin" ]; then
        echo "  SnpEff cache built successfully"
    else
        echo "  ERROR: snpEffectPredictor.bin not created"
        exit 1
    fi
else
    echo "  snpeff_cache/${DB_NAME}/snpEffectPredictor.bin already exists, skipping"
fi

echo ""
echo "=== S288C reference preparation complete ==="
echo "Files in ${OUTPUT_DIR}/:"
echo "  S288C_R64.fa                    - Reference FASTA (--fasta)"
echo "  S288C_R64.fa.fai                - FASTA index"
echo "  S288C_R64.gff3                  - GFF3 annotations (Ensembl)"
echo "  S288C_R64.gbff                  - GenBank original (NCBI, NC_* names)"
echo "  S288C_R64_ensembl_chrnames.gb   - GenBank renamed (--genbank for breseq)"
echo "  chromosomes/                    - Per-chromosome FASTAs (--chr_dir)"
echo "  snpeff_cache/                   - SnpEff cache (--snpeff_cache)"
