#!/bin/bash
run_folder="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
nextflow run ${run_folder}/nf-core-sarek_3.5.1/3_5_1/main.nf -profile azureD4as,docker \
    -w ${run_folder}/work_test_001 \
    --input ${run_folder}/assets/reads/samplesheet.csv \
    --outdir ${run_folder}/output_test_001  --genome null --igenomes_ignore \
    --fasta ${run_folder}/assets/references/draft_ref52.fasta --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config \
    --tools snpeff,haplotypecaller,freebayes,cnvkit,tiddit,manta  \
    --split_fastq 0  \
    --joint_germline --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint \
    --snpeff_cache ${run_folder}/assets/references/snpeff_cache --snpeff_db draft_ref.52 -resume
