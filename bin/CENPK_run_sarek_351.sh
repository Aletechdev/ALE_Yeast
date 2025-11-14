# run_folder="/Users/zhlia/Documents/GitRepo/ALE_nextflow"
run_folder="/home/azureuser/Docs/ALE_nextflow"  #--joint_germline \     --concatenate_vcfs \
nextflow run ../nf-core-sarek_3.5.1/3_5_1/main.nf -profile azureD4as,docker \
    -w ${run_folder}/work_CENPK_subset \
    --input ${run_folder}/data/data_a_paper/sub_sample/samplesheet.csv \
    --outdir ${run_folder}/output  --genome null --igenomes_ignore \
    --fasta ${run_folder}/data/BakerYeast_reference/draft_ref52.fasta --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config --tools snpeff,freebayes,mutect2,haplotypecaller  --split_fastq 0  \
    --joint_germline --joint_mutect2 --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint \
    --snpeff_cache ${run_folder}/data/BakerYeast_reference/snpeff_cache --snpeff_db draft_ref.52 -resume
