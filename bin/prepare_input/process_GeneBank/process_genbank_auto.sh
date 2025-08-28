#!/bin/bash

# Automated GenBank Processing Pipeline
# Processes GenBank files to generate all required formats for NextFlow Sarek pipeline
# Usage: ./process_genbank_auto.sh <input.gbk> [output_dir]

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEFAULT_OUTPUT_DIR="$(pwd)/genbank_processed"

# Docker images
readonly ANY2FASTA_IMAGE="staphb/any2fasta:0.4.2"
readonly SNPEFF_IMAGE="quay.io/biocontainers/snpeff:5.1--hdfd78af_2"

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

log_info() {
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

log_error() {
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

usage() {
    cat << 'EOF'
Usage: ./process_genbank_auto.sh <input.gbk> [output_dir]

Automatically processes GenBank files for NextFlow Sarek pipeline:
1. Extracts organism information
2. Converts GenBank to FASTA
3. Converts GenBank to GFF3
4. Generates SnpEff cache
5. Creates processing summary

Arguments:
  input.gbk    - Input GenBank file (.gbk or .gb)
  output_dir   - Output directory (optional, default: ./genbank_processed)

Example:
  ./process_genbank_auto.sh Ogataea_polymorpha.gbk ./output
EOF
}

validate_prerequisites() {
    log_info "Validating prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Pull required Docker images if not present
    for image in "${ANY2FASTA_IMAGE}" "${SNPEFF_IMAGE}"; do
        if ! docker images "${image}" --format "table {{.Repository}}:{{.Tag}}" | grep -q "${image}"; then
            log_info "Pulling Docker image: ${image}"
            docker pull "${image}"
        fi
    done
}

extract_organism_info() {
    local gbk_file="$1"
    local output_file="$2"
    
    log_info "Extracting organism information..."
    
    local organism=$(grep -m 1 "ORGANISM" "$gbk_file" | sed 's/ORGANISM[[:space:]]*//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
    local definition=$(grep -m 1 "DEFINITION" "$gbk_file" | sed 's/DEFINITION[[:space:]]*//')
    local accession=$(grep -m 1 "ACCESSION" "$gbk_file" | awk '{print $2}')
    local version=$(grep -m 1 "VERSION" "$gbk_file" | awk '{print $2}')
    
    # Generate clean genome name - handle species names properly
    local genome_name=$(echo "$organism" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | sed 's/[^a-zA-Z0-9_]/_/g' | sed 's/__*/_/g' | sed 's/^_*//' | sed 's/_*$//')
    
    cat > "$output_file" << EOF
# Organism Information (auto-extracted)
ORGANISM="$organism"
DEFINITION="$definition"
ACCESSION="$accession"
VERSION="$version"
GENOME_NAME="$genome_name"
SPECIES_SHORT="${organism}"
EOF
    
    log_info "Organism: $organism"
    log_info "Genome name: $genome_name"
}

convert_gbk_to_fasta() {
    local gbk_file="$1"
    local output_fasta="$2"
    
    log_info "Converting GenBank to FASTA..."
    
    local input_dir=$(dirname "$gbk_file")
    local output_dir=$(dirname "$output_fasta")
    local output_filename=$(basename "$output_fasta")
    
    mkdir -p "$output_dir"
    
    docker run --rm --platform=linux/amd64 \
        -v "$input_dir":/data/in:ro \
        -v "$output_dir":/data/out \
        "${ANY2FASTA_IMAGE}" \
        sh -c "any2fasta /data/in/$(basename "$gbk_file") > /data/out/$output_filename"
    
    log_info "FASTA conversion completed: $output_fasta"
}

convert_gbk_to_gff3() {
    local gbk_file="$1"
    local output_gff3="$2"
    
    log_info "Converting GenBank to GFF3..."
    
    local input_dir=$(dirname "$gbk_file")
    local output_dir=$(dirname "$output_gff3")
    local output_filename=$(basename "$output_gff3")
    
    mkdir -p "$output_dir"
    
    # Use BioPython for GenBank to GFF3 conversion
    docker run --rm \
        -v "$input_dir":/data/in:ro \
        -v "$output_dir":/data/out \
        -v "$SCRIPT_DIR":/scripts:ro \
        python:3.9-slim \
        bash -c "
        pip install biopython > /dev/null 2>&1
        python3 -c '
from Bio import SeqIO
import sys

def genbank_to_gff3(gb_file, gff_file):
    with open(gb_file, \"r\") as input_handle, open(gff_file, \"w\") as output_handle:
        output_handle.write(\"##gff-version 3\n\")
        
        for record in SeqIO.parse(input_handle, \"genbank\"):
            # Remove version suffix from chromosome name to match FASTA
            chrom_name = record.id.split(\".\")[0] if \".\" in record.id else record.id
            # Write sequence region
            output_handle.write(f\"##sequence-region {chrom_name} 1 {len(record.seq)}\n\")
            
            for feature in record.features:
                if feature.type == \"source\":
                    continue
                    
                # Extract attributes
                attributes = []
                if \"locus_tag\" in feature.qualifiers:
                    locus_tag = feature.qualifiers[\"locus_tag\"][0]
                    attributes.append(f\"ID={locus_tag}\")
                if \"product\" in feature.qualifiers:
                    product = feature.qualifiers[\"product\"][0].replace(\";\", \",\")
                    attributes.append(f\"Name={product}\")
                if \"protein_id\" in feature.qualifiers:
                    protein_id = feature.qualifiers[\"protein_id\"][0]
                    attributes.append(f\"protein_id={protein_id}\")
                
                # Handle location
                start = int(feature.location.start) + 1  # GFF is 1-based
                end = int(feature.location.end)
                strand = \"+\" if feature.location.strand == 1 else \"-\" if feature.location.strand == -1 else \".\"
                
                # Write GFF3 line
                attr_string = \";\".join(attributes) if attributes else \".\"
                output_handle.write(f\"{chrom_name}\tGenBank\t{feature.type}\t{start}\t{end}\t.\t{strand}\t.\t{attr_string}\n\")

genbank_to_gff3(\"/data/in/$(basename "$gbk_file")\", \"/data/out/$output_filename\")
print(\"GFF3 conversion completed\", file=sys.stderr)
'
        "
    
    log_info "GFF3 conversion completed: $output_gff3"
}

generate_snpeff_cache() {
    local organism_info="$1"
    local fasta_file="$2"
    local gff3_file="$3"
    local cache_dir="$4"
    
    log_info "Generating SnpEff cache..."
    
    # Source organism information
    source "$organism_info"
    
    local snpeff_cache_dir="$cache_dir/snpeff_cache"
    local data_dir="$snpeff_cache_dir/data/$GENOME_NAME"
    local genome_dir_v351="$snpeff_cache_dir/$GENOME_NAME"
    
    # Create directories
    mkdir -p "$data_dir"
    mkdir -p "$genome_dir_v351"
    
    # Copy files
    cp "$fasta_file" "$data_dir/sequences.fa"
    cp "$gff3_file" "$data_dir/genes.gff"
    
    # Create SnpEff config
    cat > "$snpeff_cache_dir/snpEff.config" << EOF
# $ORGANISM genome $GENOME_NAME
$GENOME_NAME.genome : $GENOME_NAME
EOF
    
    # Build database
    docker run --rm \
        -v "$snpeff_cache_dir":/data \
        -w /data \
        "${SNPEFF_IMAGE}" \
        snpEff build -gff3 -v "$GENOME_NAME" -noCheckCds -noCheckProtein
    
    # Setup Sarek compatibility
    cp -r "$data_dir/." "$genome_dir_v351/"
    cp "$snpeff_cache_dir/snpEff.config" "$genome_dir_v351/snpEff.config"
    
    log_info "SnpEff cache generation completed: $snpeff_cache_dir"
}

create_processing_summary() {
    local output_dir="$1"
    local organism_info="$2"
    
    source "$organism_info"
    
    cat > "$output_dir/PROCESSING_SUMMARY.md" << EOF
# GenBank Processing Summary

**Processed:** $(date)
**Input File:** $(basename "$INPUT_GBK")

## Organism Information
- **Organism:** $ORGANISM  
- **Definition:** $DEFINITION
- **Accession:** $ACCESSION
- **Version:** $VERSION
- **Genome Name:** $GENOME_NAME

## Generated Files
\`\`\`
$output_dir/
├── organism_info.sh              # Extracted organism metadata
├── $GENOME_NAME.fasta           # Reference genome FASTA
├── $GENOME_NAME.gff3           # Annotation GFF3
├── snpeff_cache/               # SnpEff annotation cache
│   ├── $GENOME_NAME/          # Sarek-compatible format
│   └── data/$GENOME_NAME/     # SnpEff data directory
└── PROCESSING_SUMMARY.md        # This summary
\`\`\`

## Usage in NextFlow Sarek

\`\`\`bash
nextflow run nf-core/sarek \\
    --input samplesheet.csv \\
    --outdir results \\
    --genome $GENOME_NAME \\
    --igenomes_ignore \\
    --fasta $output_dir/$GENOME_NAME.fasta \\
    --snpeff_cache $output_dir/snpeff_cache \\
    --snpeff_db $GENOME_NAME \\
    --skip_tools baserecalibrator \\
    --tools freebayes,mutect2,snpeff
\`\`\`

## File Validation
- FASTA sequences: $(grep -c '^>' "$output_dir/$GENOME_NAME.fasta") 
- GFF3 features: $(grep -cv '^#' "$output_dir/$GENOME_NAME.gff3")
- SnpEff database: $([ -d "$output_dir/snpeff_cache/data/$GENOME_NAME" ] && echo "✓ Generated" || echo "✗ Missing")
EOF
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    # Parse arguments
    if [[ $# -lt 1 || $# -gt 2 ]]; then
        usage
        exit 1
    fi
    
    local input_gbk="$1"
    local output_dir="${2:-$DEFAULT_OUTPUT_DIR}"
    
    # Validate input
    if [[ ! -f "$input_gbk" ]]; then
        log_error "Input GenBank file not found: $input_gbk"
        exit 1
    fi
    
    # Convert to absolute paths
    INPUT_GBK=$(realpath "$input_gbk")
    OUTPUT_DIR=$(realpath "$output_dir")
    
    log_info "Starting automated GenBank processing"
    log_info "Input: $INPUT_GBK"
    log_info "Output: $OUTPUT_DIR"
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Set up file paths
    local organism_info="$OUTPUT_DIR/organism_info.sh"
    
    # Execute processing pipeline
    validate_prerequisites
    extract_organism_info "$INPUT_GBK" "$organism_info"
    
    # Source organism info for file naming
    source "$organism_info"
    
    local fasta_file="$OUTPUT_DIR/${GENOME_NAME}.fasta"
    local gff3_file="$OUTPUT_DIR/${GENOME_NAME}.gff3"
    
    convert_gbk_to_fasta "$INPUT_GBK" "$fasta_file"
    convert_gbk_to_gff3 "$INPUT_GBK" "$gff3_file"
    generate_snpeff_cache "$organism_info" "$fasta_file" "$gff3_file" "$OUTPUT_DIR"
    create_processing_summary "$OUTPUT_DIR" "$organism_info"
    
    log_info "Automated GenBank processing completed successfully!"
    log_info "Results saved to: $OUTPUT_DIR"
    log_info "Review: $OUTPUT_DIR/PROCESSING_SUMMARY.md"
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi