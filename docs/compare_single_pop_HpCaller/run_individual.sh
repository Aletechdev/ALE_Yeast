#!/bin/bash

# Run nf-core/sarek pipeline for adipic project
# Date: 2025-11-09
# Reference: 
# Set up paths
ale_nextflow_folder="/home/azureuser/Docs/ALE_nextflow"
project_folder="/home/azureuser/Docs/ALE_nextflow/bin/compare_single_pop_HpCaller"
ref_genome_folder="/home/azureuser/Docs/ALE_nextflow/data/BakerYeast_reference"

# Reference genome information
FASTA="${ref_genome_folder}/draft_ref52.fasta"

# Run Sarek pipeline
# IMPORTANT: -c (config) must come BEFORE -profile for custom profiles to be recognized
nextflow run ${ale_nextflow_folder}/nf-core-sarek_3.5.1/3_5_1/main.nf \
    -profile azureD4as,docker \
    -w ${project_folder}/work_inde \
    --input ${project_folder}/samplesheet.csv \
    --outdir ${project_folder}/output_inde \
    --genome null \
    --igenomes_ignore \
    --fasta ${FASTA} \
    --skip_tools baserecalibrator \
    --tools haplotypecaller \
    --split_fastq 0 \
    --save_mapped \
    -resume

# Notes:
# - Using Ogataea parapolymorpha DL-1 reference genome
# - Samples: DL1_inhouse (8 lanes) + DL1_DNASense (1 lane)
# - Ploidy: 1 (haploid)
# - Tools: All variant callers enabled for comprehensive analysis
# - Joint calling enabled for both HaplotypeCaller germline
