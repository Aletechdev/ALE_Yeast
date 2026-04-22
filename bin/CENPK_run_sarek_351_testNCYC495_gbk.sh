#!/bin/bash
# Quick test: Ogataea polymorpha NCYC495 with subsampled data
data_folder="/home/azureuser/Docs/ALE_nextflow"
pipeline_folder="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd ${data_folder}/bin
nextflow run ${pipeline_folder}/main.nf -profile azureD4as,docker \
    --input ${data_folder}/data/data_a_paper/sub_sample/samplesheet.csv \
    --outdir ${data_folder}/output_quick_test_NCYC495  --genome null --igenomes_ignore \
    --fasta ${data_folder}/data/Yeast_methanol_RWTH/Ogataea_polymorpha_NCYC495/processed/ogataea_polymorpha.fasta --skip_tools baserecalibrator \
    --tools snpeff,freebayes --split_fastq 0  \
    --snpeff_cache ${data_folder}/data/Yeast_methanol_RWTH/Ogataea_polymorpha_NCYC495/processed/snpeff_cache --snpeff_db ogataea_polymorpha -resume
