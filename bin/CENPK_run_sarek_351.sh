# run_folder="/Users/zhlia/Documents/GitRepo/NF_ALE"
run_folder="/Users/zhiweili/Documents/Repo/NF_ALE"
nextflow run ../nf-core-sarek_3.5.1/3_5_1/main.nf -profile arm,docker \
    --input ${run_folder}/data/data_a_paper/sub_sample/samplesheet.csv \
    --outdir ${run_folder}/output  --genome draft_ref.52 --igenomes_ignore \
    --fasta ${run_folder}/data/BakerYeast_reference/draft_ref52.fasta --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config --tools freebayes,snpeff,haplotypecaller --split_fastq 0  \
    --concatenate_vcfs --joint_germline \
    --snpeff_cache ${run_folder}/data/BakerYeast_reference/snpeff_cache --snpeff_db draft_ref.52 -resume