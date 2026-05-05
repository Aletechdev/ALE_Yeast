#!/bin/bash
# Ottilie Benchmark - Subsampled validation run (4 samples, ~16x coverage)
# Purpose: Verify reference genome, SnpEff cache, and pipeline configuration
# Status: COMPLETED SUCCESSFULLY - all 4 samples pass including Control-FREEC
# Subsampled with: seqtk sample -s42 <fastq> 1000000 (1M read pairs per sample)
# Output: output_ottilie_sub/

set -euo pipefail

run_folder="/home/azureuser/Docs/ALE_nextflow"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate /home/azureuser/miniforge3/envs/nf-env

nextflow run ${run_folder}/nf-core-sarek_3.5.1/3_5_1/main.nf \
    -profile azureD4as,docker \
    -w ${run_folder}/work_ottilie_sub \
    --input ${run_folder}/data/ottilie/samplesheet_pilot_subsampled.csv \
    --outdir ${run_folder}/output_ottilie_sub \
    --genome null \
    --igenomes_ignore \
    --fasta ${run_folder}/data/ottilie/S288C_reference/S288C_R64.fa \
    --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config \
    --tools snpeff,cnvkit,controlfreec,haplotypecaller \
    --chr_dir ${run_folder}/data/ottilie/S288C_reference/chromosomes \
    --genbank ${run_folder}/data/ottilie/S288C_reference/S288C_R64_ensembl_chrnames.gb \
    --split_fastq 0 \
    --joint_germline \
    --save_mapped \
    --split_haplotypecaller_joint_vcf \
    --hard_filter_haplotypecaller_joint \
    --snpeff_db R64-1-1.105 \
    --snpeff_cache ${run_folder}/data/ottilie/S288C_reference/snpeff_cache \
    -resume
