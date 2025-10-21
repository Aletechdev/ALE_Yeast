run_folder="/home/azureuser/Docs/ALE_nextflow"  #--joint_germline \     --concatenate_vcfs \
nextflow run ./nf-core-sarek_3.5.1/3_5_1/main.nf -profile test_ALE_Yeast,azureD4as,docker \
    -w ${run_folder}/work_test_001 \
    --input ${run_folder}/assets/reads/samplesheet.csv \
    --outdir ${run_folder}/output_test_001  --genome null --igenomes_ignore \
    --fasta ${run_folder}/assets/references/draft_ref52.fasta --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config --tools snpeff,mutect2,haplotypecaller,freebayes  --split_fastq 0  \
    --joint_germline --joint_mutect2 --split_haplotypecaller_joint_vcf \
    --snpeff_cache ${run_folder}/assets/references/snpeff_cache --snpeff_db draft_ref.52 -resume
