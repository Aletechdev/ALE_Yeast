#!/bin/bash
# Note: controlfreec excluded - sub-sampled test data has insufficient read depth for GC normalization.
# Use CENPK_run_sarek_351_all.sh with full data to test controlfreec.
run_folder="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
nextflow run ${run_folder}/main.nf -profile azureD4as,docker \
    -w ${run_folder}/work_test_001 \
    --input ${run_folder}/assets/reads/samplesheet.csv \
    --outdir ${run_folder}/output_test_001  --genome null --igenomes_ignore \
    --fasta ${run_folder}/assets/references/draft_ref52.fasta --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config \
    --tools snpeff,haplotypecaller,freebayes,cnvkit,tiddit,manta,breseq  \
    --genbank ${run_folder}/assets/references/draft_ref52.gff3 \
    --split_fastq 0  \
    --joint_germline --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint \
    --snpeff_cache ${run_folder}/assets/references/snpeff_cache --snpeff_db draft_ref.52 -resume
