run_folder="/Users/zhlia/Documents/GitRepo/NF_ALE"
nextflow run nf-core/sarek -r 3.4.0 -profile docker \
    --input ${run_folder}/data/data_a_paper/samplesheet_m3.csv \
    --outdir ${run_folder}/output_a_paper_noMutect  --genome draft_ref.52 --igenomes_ignore \
    --fasta ${run_folder}/data/BakerYeast_reference/draft_ref52.fasta --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config --tools freebayes,manta,snpeff --split_fastq 50000000  \
    --snpeff_cache ${run_folder}/data/BakerYeast_reference/snpeff_cache --snpeff_db draft_ref.52 -resume