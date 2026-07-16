#!/bin/bash
# Ottilie Benchmark - Tier 2 run (86 samples: 1 parent + 85 CRISPR-validated clones)
# Reference: S288C R64-1-1 (Ensembl) with built-in SnpEff R64-1-1.105
# Tools: snpeff, tiddit, manta, cnvkit, controlfreec, haplotypecaller
# Output: output_ottilie_tier2/
# Expected runtime: ~2-4 days on D4as (4 vCPU, 16 GB RAM)
# See TODO_tier2_local_run.md for joint calling OOM fallback plan

set -euo pipefail

run_folder="/home/azureuser/Docs/ALE_nextflow"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate /home/azureuser/miniforge3/envs/nf-env

nextflow run ${run_folder}/main.nf \
    -profile azureD4as,docker \
    -w ${run_folder}/work_ottilie_tier2 \
    --input ${run_folder}/data/ottilie/samplesheet_tier2.csv \
    --outdir ${run_folder}/output_ottilie_tier2 \
    --genome null \
    --igenomes_ignore \
    --fasta ${run_folder}/data/ottilie/S288C_reference/S288C_R64.fa \
    --skip_tools baserecalibrator \
    --tools snpeff,cnvkit,tiddit,manta,haplotypecaller \
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
