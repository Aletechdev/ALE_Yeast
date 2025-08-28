# run_folder="/Users/zhlia/Documents/GitRepo/ALE_nextflow"
run_folder="/home/azureuser/Docs/ALE_nextflow"  #--joint_germline \     --concatenate_vcfs \
nextflow run ../nf-core-sarek_3.5.1/3_5_1/main.nf -profile azureD4as,docker \
    --input ${run_folder}/data/Yeast_methanol_RWTH/Ogataea_polymorpha_NCYC495/sarek_samplesheet.csv \
    --outdir ${run_folder}/output_NCYC495  --genome null --igenomes_ignore \
    --fasta ${run_folder}/data/Yeast_methanol_RWTH/Ogataea_polymorpha_NCYC495/processed/ogataea_polymorpha.fasta --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config --tools snpeff,freebayes --split_fastq 0  \
    --snpeff_cache ${run_folder}/data/Yeast_methanol_RWTH/Ogataea_polymorpha_NCYC495/processed/snpeff_cache --snpeff_db ogataea_polymorpha -resume
