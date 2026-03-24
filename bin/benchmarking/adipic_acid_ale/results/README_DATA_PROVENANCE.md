# Data Provenance

## Study

**Pereira et al. (2019)** "Elucidating aromatic acid tolerance at low pH in *Saccharomyces cerevisiae* using adaptive laboratory evolution"
- DOI: [10.1016/j.ymben.2019.09.008](https://doi.org/10.1016/j.ymben.2019.09.008)
- Organism: *Saccharomyces cerevisiae* CEN.PK113-7D

## Truth Set

Curated from published supplementary tables:
- **Table S5**: All mutations identified across ALE lineages
- **Table S8**: Spore-seq segregation data (tolerant vs sensitive spores)

Processing pipeline: `data/dicarboxylic_acids/process_adipic_muts/`
```
01_parse_table_s5.py      → 01_table_s5_adipic_mutations.csv
02_parse_table_s8.py      → 02_table_s8_tolerant_sensitive.csv
03_map_mutations_to_genomic.py → 03_table_s8_genomic_locations.csv  ← used by benchmarking
```

The final truth set (`03_table_s8_genomic_locations.csv`) contains 24 SNVs with:
- Genomic coordinates (chrom, pos, ref, alt) mapped to draft_ref52 reference
- Expected allele frequencies from spore-seq segregation (positive/negative strain pairs)
- 3 negative controls (mutations expected at 0% in specific strains)

## Raw Sequencing Data

**Status**: Private — not included in this repository.

**17 samples**: 7 clonal isolates (I1) + 10 population samples (I2/I3)
- Clonal: Single-colony isolates from evolved lineages
- Population: Spore-seq pools (~100 spores per pool, sequenced as bulk)

A canonical copy of all inputs (FASTQs, reference genome, annotation, SnpEff cache, and samplesheet) is on Azure Blob Storage:
```
https://aledata.blob.core.windows.net/aledata/Yeast/adipic_acid_ale_benchmark/
├── data_a_paper/
│   ├── samplesheet_gen2_allNormal_changePloidy.csv
│   ├── *.fastq.gz                        # 56 clonal FASTQs (7 samples × 4 lanes × R1/R2)
│   └── spore_seq/Adipic_acid/batch*/     # 80 spore-seq FASTQs (10 samples × 4 lanes × R1/R2)
└── BakerYeast_reference/
    ├── draft_ref52.fasta                  # Reference genome
    ├── draft_ref52.gff3                   # Gene annotation (used by breseq via --genbank)
    └── snpeff_cache/                      # SnpEff annotation database
```

Upload/download scripts: `bin/prepare_input/upload_adipic_acid_ale_benchmark.sh` / `download_adipic_acid_ale_benchmark.sh`

## Reference Genome

- **File**: `data/BakerYeast_reference/draft_ref52.fasta`
- **Annotation**: `data/BakerYeast_reference/draft_ref52.gff3`
- **Origin**: Modified CEN.PK113-7D assembly (17 scaffolds, 12.4 Mb)
- **BUSCO**: 99.3% complete (saccharomycetes_odb10)
- **Note**: Not the S288C reference — specific to this strain background

## Pipeline Inputs

### Samplesheet
- **File**: `data/data_a_paper/samplesheet_gen2_allNormal_changePloidy.csv`
- **Generator**: `bin/prepare_input/generate_sarek_csv.py`
- **Format**: Sarek CSV with columns: experiment, sample, status, clonal_or_population, ploidy, sex, lane, fastq_1, fastq_2
- **Key settings**: All samples status=0 (normal) for joint germline calling; ploidy=1 (clonal) or ploidy=10 (population)

### Pipeline Command
```bash
nextflow run ../nf-core-sarek_3.5.1/3_5_1/main.nf -profile azureD4as,docker \
    -w ${run_folder}/work_CENPK \
    --input ${run_folder}/data/data_a_paper/samplesheet_gen2_allNormal_changePloidy.csv \
    --outdir ${run_folder}/output_all --genome null --igenomes_ignore \
    --fasta ${run_folder}/data/BakerYeast_reference/draft_ref52.fasta \
    --skip_tools baserecalibrator \
    -c ${run_folder}/bin/nextflow.config \
    --tools snpeff,freebayes,manta,cnvkit,tiddit,haplotypecaller,deepvariant,breseq \
    --genbank ${run_folder}/data/BakerYeast_reference/draft_ref52.gff3 \
    --split_fastq 0 \
    --joint_germline --save_mapped \
    --split_haplotypecaller_joint_vcf --hard_filter_haplotypecaller_joint \
    --snpeff_cache ${run_folder}/data/BakerYeast_reference/snpeff_cache \
    --snpeff_db draft_ref.52 -resume
```

**Key flags for benchmarking**:
- `--tools haplotypecaller,breseq` — the two tools being compared
- `--joint_germline` — enables HaplotypeCaller joint calling across all samples
- `--split_haplotypecaller_joint_vcf` — extracts individual sample VCFs from joint VCF
- `--hard_filter_haplotypecaller_joint` — applies dynamic AF hard filter (>=90% clonal, >=5% population)

## Reproducing Results

1. Obtain raw FASTQ data (requires access to Azure Blob Storage)
2. Run the Sarek pipeline: `bash bin/CENPK_run_sarek_351_all.sh`
3. Run benchmarking scripts in order:
   ```bash
   source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
   python bin/benchmarking/adipic_acid_ale/01_precision_recall.py
   python bin/benchmarking/adipic_acid_ale/02_tool_comparison.py
   python bin/benchmarking/adipic_acid_ale/03_summary_report.py
   bash bin/benchmarking/adipic_acid_ale/04_update_results.sh
   ```
4. Outputs written to `output_all/` and snapshot committed here in `results/`
