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

Raw FASTQ files are stored on Azure Blob Storage:
```
https://aledata.blob.core.windows.net/aledata/Yeast/dicarboxylic_acids_all_clones/
```

**17 samples**: 7 clonal isolates (I1) + 10 population samples (I2/I3)
- Clonal: Single-colony isolates from evolved lineages
- Population: Spore-seq pools (~100 spores per pool, sequenced as bulk)

## Reference Genome

- **File**: `assets/references/draft_ref52.fasta`
- **Origin**: Modified CEN.PK113-7D assembly (17 scaffolds, 12.4 Mb)
- **BUSCO**: 99.3% complete (saccharomycetes_odb10)
- **Note**: Not the S288C reference — specific to this strain background

## Reproducing Results

1. Obtain raw FASTQ data (requires access to Azure Blob Storage)
2. Run the Sarek pipeline: `bash bin/CENPK_run_sarek_351_all.sh`
3. Run benchmarking scripts in order:
   ```bash
   source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
   python bin/benchmarking/01_precision_recall.py
   python bin/benchmarking/02_tool_comparison.py
   python bin/benchmarking/03_summary_report.py
   ```
4. Outputs written to `output_all/` and snapshot committed here in `results/`
