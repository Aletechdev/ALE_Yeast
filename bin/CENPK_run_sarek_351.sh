# run_folder="/Users/zhlia/Documents/GitRepo/NF_ALE"
run_folder="/home/azureuser/Docs/NF_ALE"  #--joint_germline \     --concatenate_vcfs \
nextflow run ../nf-core-sarek_3.5.1/3_5_1/main.nf -profile azureD4as,docker \
    --input ${run_folder}/data/data_a_paper/sub_sample/samplesheet.csv \
    --outdir ${run_folder}/output  --genome null --igenomes_ignore \
    --fasta ${run_folder}/data/BakerYeast_reference/draft_ref52.fasta --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config --tools snpeff,mutect2,freebayes,haplotypecaller --split_fastq 0  \
    --snpeff_cache ${run_folder}/data/BakerYeast_reference/snpeff_cache --snpeff_db draft_ref.52 -resume

   