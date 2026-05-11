#!/bin/bash
# Ottilie Benchmark - Full-depth pilot run (4 samples)
# Status: COMPLETED SUCCESSFULLY
# Reference: S288C R64-1-1 (Ensembl) with built-in SnpEff R64-1-1.105
# Samples: 1 parent (NODRUG-GM2) + 3 evolved (Doxorubicin, Carmaphycin, CBR110)
# Tools: snpeff, tiddit, cnvkit, controlfreec, haplotypecaller
# Output: output_ottilie/

set -euo pipefail

run_folder="/home/azureuser/Docs/ALE_nextflow"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate /home/azureuser/miniforge3/envs/nf-env

nextflow run ${run_folder}/main.nf \
    -profile azureD4as,docker \
    -w ${run_folder}/work_ottilie \
    --input ${run_folder}/data/ottilie/samplesheet_pilot.csv \
    --outdir ${run_folder}/output_ottilie \
    --genome null \
    --igenomes_ignore \
    --fasta ${run_folder}/data/ottilie/S288C_reference/S288C_R64.fa \
    --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config \
    --tools snpeff,cnvkit,tiddit,controlfreec,haplotypecaller \
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
