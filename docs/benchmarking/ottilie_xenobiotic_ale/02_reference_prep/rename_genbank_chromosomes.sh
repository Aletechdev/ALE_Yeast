#!/bin/bash
# Rename NCBI RefSeq accessions to Ensembl-style Roman numeral chromosome names
# in S288C R64 GenBank file, for consistency with the rest of the pipeline.
#
# Source: https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/146/045/GCF_000146045.2_R64/GCF_000146045.2_R64_genomic.gbff.gz
# Mapping based on NCBI assembly GCF_000146045.2 chromosome assignments.

set -euo pipefail

INPUT="${1:-data/ottilie/S288C_reference/S288C_R64.gbff}"
OUTPUT="${2:-data/ottilie/S288C_reference/S288C_R64_ensembl_chrnames.gb}"

if [ ! -f "$INPUT" ]; then
    echo "ERROR: Input file not found: $INPUT"
    exit 1
fi

# NC_* accession to Ensembl Roman numeral mapping (from NCBI GCF_000146045.2)
sed \
    -e 's/NC_001133\.9/I/g'     \
    -e 's/NC_001133/I/g'        \
    -e 's/NC_001134\.8/II/g'    \
    -e 's/NC_001134/II/g'       \
    -e 's/NC_001135\.5/III/g'   \
    -e 's/NC_001135/III/g'      \
    -e 's/NC_001136\.10/IV/g'   \
    -e 's/NC_001136/IV/g'       \
    -e 's/NC_001137\.3/V/g'     \
    -e 's/NC_001137/V/g'        \
    -e 's/NC_001138\.5/VI/g'    \
    -e 's/NC_001138/VI/g'       \
    -e 's/NC_001139\.9/VII/g'   \
    -e 's/NC_001139/VII/g'      \
    -e 's/NC_001140\.6/VIII/g'  \
    -e 's/NC_001140/VIII/g'     \
    -e 's/NC_001141\.2/IX/g'    \
    -e 's/NC_001141/IX/g'       \
    -e 's/NC_001142\.9/X/g'     \
    -e 's/NC_001142/X/g'        \
    -e 's/NC_001143\.9/XI/g'    \
    -e 's/NC_001143/XI/g'       \
    -e 's/NC_001144\.5/XII/g'   \
    -e 's/NC_001144/XII/g'      \
    -e 's/NC_001145\.3/XIII/g'  \
    -e 's/NC_001145/XIII/g'     \
    -e 's/NC_001146\.8/XIV/g'   \
    -e 's/NC_001146/XIV/g'      \
    -e 's/NC_001147\.6/XV/g'    \
    -e 's/NC_001147/XV/g'       \
    -e 's/NC_001148\.4/XVI/g'   \
    -e 's/NC_001148/XVI/g'      \
    -e 's/NC_001224\.1/Mito/g'  \
    -e 's/NC_001224/Mito/g'     \
    "$INPUT" > "$OUTPUT"

echo "Renamed chromosomes: $INPUT -> $OUTPUT"
echo "Verification (LOCUS lines):"
grep "^LOCUS" "$OUTPUT"
