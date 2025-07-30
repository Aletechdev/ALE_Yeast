
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

# Configuration variables
data_folder="/Users/zhlia/Documents/GitRepo/NF_ALE/data/BakerYeast_reference"
species="Saccharomyces_cerevisiae"
genome_name="draft_ref"
version="52"

# Build for SnpEff
# Source: https://pcingola.github.io/SnpEff/snpeff/build_db/#step-1-configure-a-new-genome

echo "Setting up SnpEff cache directories..."

# Create main cache directory
snpEff_cache_folder="${data_folder}/snpeff_cache"
mkdir -p "${snpEff_cache_folder}"

# Create SnpEff data directory
snpeff_data_folder="${snpEff_cache_folder}/data/${genome_name}.${version}"
mkdir -p "${snpeff_data_folder}"

# Create Sarek compatibility directories
snpEff_genome_folder_v351="${snpEff_cache_folder}/${genome_name}.${version}"  # for Sarek 3.5.1
mkdir -p "${snpEff_genome_folder_v351}"

snpEff_genome_folder_v340="${snpEff_cache_folder}/${genome_name}.${version}.${genome_name}.${version}"  # for Sarek 3.4.0
mkdir -p "${snpEff_genome_folder_v340}"

# Step 1: Configure new genome
echo "Configuring SnpEff genome..."
echo "# ${species} genome ${genome_name}, version ${version}" > "${snpEff_cache_folder}/snpEff.config"
echo "${genome_name}.${version}.genome : ${genome_name}.${version}" >> "${snpEff_cache_folder}/snpEff.config"

# Copy and clean GFF file
echo "Processing GFF file..."
cp "${data_folder}/draft_ref52.gff3" "${snpeff_data_folder}/draft_ref52.gff3"
# Remove 'source' entries from GFF file (third column)
awk -F'\t' '$3 != "source"' "${snpeff_data_folder}/draft_ref52.gff3" > "${snpeff_data_folder}/genes.gff"

# Build SnpEff database
echo "Building SnpEff database..."
docker run --rm \
    -v "${snpEff_cache_folder}:/data" \
    -w /data \
    quay.io/biocontainers/snpeff:5.1--hdfd78af_2 \
    snpEff build -gff3 -v draft_ref.52 -noCheckCds -noCheckProtein

# Configure for Sarek 3.4.0 compatibility
echo "Setting up Sarek compatibility..."
echo "${genome_name}.${version}.${genome_name}.${version}.genome : ${genome_name}.${version}" >> "${snpEff_genome_folder_v340}/snpEff.config"

# Set proper permissions
chmod 644 "${snpEff_cache_folder}/snpEff.config"
chmod 644 "${snpEff_genome_folder_v340}/snpEff.config"

# Copy data to compatibility directories
cp -r "${snpeff_data_folder}/." "${snpEff_genome_folder_v351}"
cp -r "${snpeff_data_folder}/." "${snpEff_genome_folder_v340}"

# Create null directory for Sarek input check
mkdir -p "${snpEff_cache_folder}/null.${genome_name}.${version}"

# Add config files to genome folders for Sarek compatibility
cp "${snpEff_cache_folder}/snpEff.config" "${snpEff_genome_folder_v351}/snpEff.config"

# Fix permissions for GFF3 files (Docker user ID mapping compatibility)
echo "Setting file permissions..."
find "${snpEff_cache_folder}" -name "*.gff3" -exec chmod 644 {} \;

echo "SnpEff cache generation completed successfully!"

# VEP cache setup (commented out)
# echo "Setting up VEP cache..."
# vep_cache_folder="${data_folder}/vep_cache/${species}/${version}_${genome_name}/"
# mkdir -p "${vep_cache_folder}"

# Example Sarek pipeline command:
# nextflow run nf-core/sarek -r 3.4.0 -profile docker \
#     --input /path/to/samplesheet.csv \
#     --outdir /path/to/output \
#     --genome draft_ref.52 \
#     --igenomes_ignore \
#     --fasta /path/to/draft_ref52.fasta \
#     --skip_tools baserecalibrator \
#     -c /path/to/nextflow.config \
#     --tools freebayes,mutect2,cnvkit,snpeff \
#     --split_fastq 0 \
#     --snpeff_cache "${data_folder}/snpeff_cache" \
#     --snpeff_db draft_ref.52