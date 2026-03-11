# run_folder="/Users/zhlia/Documents/GitRepo/NF_ALE"
run_folder="/home/azureuser/Docs/ALE_nextflow"  #--joint_germline \     --concatenate_vcfs \
nextflow run ../nf-core-sarek_3.5.1/3_5_1/main.nf -profile azureD4as,docker \
    -w ${run_folder}/work_CENPK \
    --input ${run_folder}/data/data_a_paper/samplesheet_gen2_allNormal_changePloidy.csv \
    --outdir ${run_folder}/output_all  --genome null --igenomes_ignore  \
    --fasta ${run_folder}/data/BakerYeast_reference/draft_ref52.fasta --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config --tools snpeff,freebayes,manta,cnvkit,tiddit,haplotypecaller,deepvariant,breseq \
    --genbank ${run_folder}/assets/references/draft_ref52.gff3 \
    --split_fastq 0  \
    --joint_germline --save_mapped --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint \
    --snpeff_cache ${run_folder}/data/BakerYeast_reference/snpeff_cache --snpeff_db draft_ref.52 -resume
