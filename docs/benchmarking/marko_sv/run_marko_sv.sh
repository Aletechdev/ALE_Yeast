#!/bin/bash
# Marko SV Benchmark - E. coli K-12 MG1655 single sample
# Reference: U00096.3 (NCBI) with custom SnpEff cache
# Samples: 1 sample (SRR6281661), haploid, status=0
# Tools: snpeff, haplotypecaller, cnvkit, tiddit, manta, controlfreec
# Output: output_marko_sv/
# NOTE: --joint_germline may fail with only 1 sample
# NOTE: Control-FREEC may still error on single-sample haploid data (see CLAUDE.md ASSESS_SIGNIFICANCE)

set -euo pipefail

run_folder="/home/azureuser/Docs/ALE_nextflow"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate /home/azureuser/miniforge3/envs/nf-env

nextflow run ${run_folder}/main.nf \
    -profile azureD4as,docker \
    -w ${run_folder}/work_marko_sv \
    --input ${run_folder}/data/marko_SV/samplesheet.csv \
    --outdir ${run_folder}/output_marko_sv \
    --genome null \
    --igenomes_ignore \
    --fasta ${run_folder}/data/marko_SV/reference/genbank_processed/escherichia_coli_str_k_12_substr_mg1655.fasta \
    --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config \
    --tools snpeff,cnvkit,tiddit,manta,controlfreec,haplotypecaller,breseq \
    --genbank ${run_folder}/data/marko_SV/reference/U00096.3.gbk \
    --split_fastq 0 \
    --save_mapped \
    --joint_germline \
    --split_haplotypecaller_joint_vcf \
    --hard_filter_haplotypecaller_joint \
    --chr_dir ${run_folder}/data/marko_SV/reference/genbank_processed/chromosomes \
    --snpeff_db escherichia_coli_str_k_12_substr_mg1655 \
    --snpeff_cache ${run_folder}/data/marko_SV/reference/genbank_processed/snpeff_cache \
    -resume