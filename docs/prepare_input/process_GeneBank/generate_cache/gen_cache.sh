
#!/bin/bash

# Generate SnpEff cache for Sarek pipeline
# Directory structure:
# /data/
# ├─ snpeff_cache/
# │  ├─ draft_ref.52/
# │  │  ├─ snpEff.config
# │  │  ├─ genome.fa
# │  │  ├─ genes.gff
# ├─ vep_cache/
# │  ├─ Saccharomyces_cerevisiae/
# │  │  ├─ 52_draft/

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

# Configuration variables
readonly DATA_FOLDER="/home/azureuser/Docs/NF_ALE/data/BakerYeast_reference"
readonly SPECIES="Saccharomyces_cerevisiae"
readonly GENOME_NAME="draft_ref"
readonly VERSION="52"
readonly SNPEFF_DOCKER_IMAGE="quay.io/biocontainers/snpeff:5.1--hdfd78af_2"

# Derived paths
readonly SNPEFF_CACHE_FOLDER="${DATA_FOLDER}/snpeff_cache"
readonly SNPEFF_DATA_FOLDER="${SNPEFF_CACHE_FOLDER}/data/${GENOME_NAME}.${VERSION}"
readonly SNPEFF_GENOME_FOLDER_V351="${SNPEFF_CACHE_FOLDER}/${GENOME_NAME}.${VERSION}"
readonly SNPEFF_GENOME_FOLDER_V340="${SNPEFF_CACHE_FOLDER}/${GENOME_NAME}.${VERSION}.${GENOME_NAME}.${VERSION}"

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

log_info() {
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

log_error() {
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

cleanup_on_error() {
    log_error "Script failed. Cleaning up incomplete cache directories..."
    rm -rf "${SNPEFF_CACHE_FOLDER}" 2>/dev/null || true
}

validate_prerequisites() {
    log_info "Validating prerequisites..."
    
    if [[ ! -f "${DATA_FOLDER}/draft_ref52.gff3" ]]; then
        log_error "Required GFF3 file not found: ${DATA_FOLDER}/draft_ref52.gff3"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker images "${SNPEFF_DOCKER_IMAGE}" --format "table {{.Repository}}:{{.Tag}}" | grep -q "${SNPEFF_DOCKER_IMAGE}"; then
        log_info "Pulling SnpEff Docker image..."
        docker pull "${SNPEFF_DOCKER_IMAGE}"
    fi
}

# =============================================================================
# CORE FUNCTIONS
# =============================================================================

create_directories() {
    log_info "Creating SnpEff cache directories..."
    
    mkdir -p "${SNPEFF_CACHE_FOLDER}"
    mkdir -p "${SNPEFF_DATA_FOLDER}"
    mkdir -p "${SNPEFF_GENOME_FOLDER_V351}"  # for Sarek 3.5.1
    mkdir -p "${SNPEFF_GENOME_FOLDER_V340}"  # for Sarek 3.4.0
    mkdir -p "${SNPEFF_CACHE_FOLDER}/null.${GENOME_NAME}.${VERSION}"  # for Sarek input check
}

configure_snpeff_genome() {
    log_info "Configuring SnpEff genome..."
    
    cat > "${SNPEFF_CACHE_FOLDER}/snpEff.config" << EOF
# ${SPECIES} genome ${GENOME_NAME}, version ${VERSION}
${GENOME_NAME}.${VERSION}.genome : ${GENOME_NAME}.${VERSION}
EOF
}

process_gff_file() {
    log_info "Processing GFF file..."
    
    local source_gff="${DATA_FOLDER}/draft_ref52.gff3"
    local temp_gff="${SNPEFF_DATA_FOLDER}/draft_ref52.gff3"
    local clean_gff="${SNPEFF_DATA_FOLDER}/genes.gff"
    
    cp "${source_gff}" "${temp_gff}"
    
    # Remove 'source' entries from GFF file (third column)
    awk -F'\t' '$3 != "source"' "${temp_gff}" > "${clean_gff}"
    
    log_info "GFF file processed: $(wc -l < "${clean_gff}") features"
}

build_snpeff_database() {
    log_info "Building SnpEff database..."
    
    if ! docker run --rm \
        -v "${SNPEFF_CACHE_FOLDER}:/data" \
        -w /data \
        "${SNPEFF_DOCKER_IMAGE}" \
        snpEff build -gff3 -v "${GENOME_NAME}.${VERSION}" -noCheckCds -noCheckProtein; then
        log_error "SnpEff database build failed"
        return 1
    fi
    
    log_info "SnpEff database build completed successfully"
}

setup_sarek_compatibility() {
    log_info "Setting up Sarek compatibility..."
    
    # Configure for Sarek 3.4.0 compatibility
    cat > "${SNPEFF_GENOME_FOLDER_V340}/snpEff.config" << EOF
${GENOME_NAME}.${VERSION}.${GENOME_NAME}.${VERSION}.genome : ${GENOME_NAME}.${VERSION}
EOF
    
    # Copy data to compatibility directories
    cp -r "${SNPEFF_DATA_FOLDER}/." "${SNPEFF_GENOME_FOLDER_V351}"
    cp -r "${SNPEFF_DATA_FOLDER}/." "${SNPEFF_GENOME_FOLDER_V340}"
    
    # Add config files to genome folders for Sarek compatibility
    cp "${SNPEFF_CACHE_FOLDER}/snpEff.config" "${SNPEFF_GENOME_FOLDER_V351}/snpEff.config"
    
    log_info "Sarek compatibility setup completed"
}

set_permissions() {
    log_info "Setting file permissions..."
    
    # Set proper permissions for config files
    chmod 644 "${SNPEFF_CACHE_FOLDER}/snpEff.config"
    chmod 644 "${SNPEFF_GENOME_FOLDER_V340}/snpEff.config"
    chmod 644 "${SNPEFF_GENOME_FOLDER_V351}/snpEff.config"
    
    # Fix permissions for GFF3 files (Docker user ID mapping compatibility)
    find "${SNPEFF_CACHE_FOLDER}" -name "*.gff3" -exec chmod 644 {} \;
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    log_info "Starting SnpEff cache generation for ${SPECIES} ${GENOME_NAME}.${VERSION}"
    
    # Set up error handling
    trap cleanup_on_error ERR
    
    # Execute pipeline steps
    validate_prerequisites
    create_directories
    configure_snpeff_genome
    process_gff_file
    build_snpeff_database
    setup_sarek_compatibility
    set_permissions
    
    log_info "SnpEff cache generation completed successfully!"
    log_info "Cache location: ${SNPEFF_CACHE_FOLDER}"
    
    # Display usage information
    cat << 'EOF'

# =============================================================================
# USAGE EXAMPLE
# =============================================================================

# Example Sarek pipeline command:
nextflow run nf-core/sarek -r 3.4.0 -profile docker \
    --input /path/to/samplesheet.csv \
    --outdir /path/to/output \
    --genome draft_ref.52 \
    --igenomes_ignore \
    --fasta /path/to/draft_ref52.fasta \
    --skip_tools baserecalibrator \
    -c /path/to/nextflow.config \
    --tools freebayes,mutect2,cnvkit,snpeff \
    --split_fastq 0 \
    --snpeff_cache /path/to/snpeff_cache \
    --snpeff_db draft_ref.52
EOF
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi