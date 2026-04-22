#!/bin/bash
# Production run: full tool suite on CEN.PK yeast ALE data
# Uses pipeline code from the repo root (after Option B restructure)
# Data lives in the main repo; pipeline code is resolved from script location
data_folder="/home/azureuser/Docs/ALE_nextflow"
pipeline_folder="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Run from bin/ so relative paths in samplesheet (../data/...) resolve correctly
cd ${data_folder}/bin
nextflow run ${pipeline_folder}/main.nf -profile azureD4as,docker \
    -w ${data_folder}/work_CENPK \
    --input ${data_folder}/data/data_a_paper/samplesheet_gen2_allNormal_changePloidy.csv \
    --outdir ${data_folder}/output_all  --genome null --igenomes_ignore  \
    --fasta ${data_folder}/data/BakerYeast_reference/draft_ref52.fasta --skip_tools baserecalibrator \
    --tools snpeff,freebayes,manta,cnvkit,controlfreec,tiddit,haplotypecaller,deepvariant,breseq \
    --chr_dir ${pipeline_folder}/assets/references/chromosomes \
    --genbank ${data_folder}/assets/references/draft_ref52.gff3 \
    --split_fastq 0  \
    --joint_germline --save_mapped --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint \
    --snpeff_cache ${data_folder}/data/BakerYeast_reference/snpeff_cache --snpeff_db draft_ref.52 -resume
