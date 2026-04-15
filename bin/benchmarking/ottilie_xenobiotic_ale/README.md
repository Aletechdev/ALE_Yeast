# Ottilie Xenobiotic ALE Benchmark

Benchmarking the NF_ALE Sarek pipeline against published variant calls from [Ottilie et al. (2022)](https://doi.org/10.1038/s42003-022-03076-7), a large-scale yeast ALE study with 363 drug-resistant clones.

## Quick Start

```bash
# Prerequisites: conda activate nf-env, Docker running

# 1. Download pilot FASTQ data (4 samples, ~4 GB)
bash 01_data_retrieval/download_pilot_fastq.sh

# 2. Prepare S288C reference genome + SnpEff cache
bash 02_reference_prep/prepare_s288c_reference.sh

# 3. Run Sarek pipeline
bash 03_pipeline/run_ottilie_pilot.sh
```

## Directory Structure

```
ottilie_xenobiotic_ale/
├── 01_data_retrieval/          # SRA data download and sample resolution
│   ├── environment_data_retrieval.yml  # Conda env (sra-tools pinned to 3.2.1)
│   ├── inspect_supplementary.py        # Parse Ottilie supplementary xlsx files
│   ├── resolve_sra_accessions.py       # Map sample names across sources
│   ├── validate_dictionary.py          # Validate resolved sample mappings
│   └── download_pilot_fastq.sh         # Download 4 pilot FASTQs from SRA
│
├── 02_reference_prep/          # S288C R64-1-1 reference setup
│   ├── prepare_s288c_reference.sh      # Master script (all 5 steps, idempotent)
│   └── rename_genbank_chromosomes.sh   # NC_* -> Roman numeral chr names
│
├── 03_pipeline/                # Sarek execution
│   └── run_ottilie_pilot.sh            # Launch pilot benchmark (4 samples)
│
├── docs/                       # Background documentation
│   ├── Nextflow_Pipeline_Benchmark_Project_Plan.md
│   └── RESEARCH_CONTEXT.md
│
└── README.md                   # This file
```

### Data Files (generated, not in this directory)

```
data/ottilie/
├── fastq/                      # Downloaded FASTQ files
├── samplesheet_pilot.csv       # Sarek input (4 pilot samples)
├── sample_name_dictionary.csv  # Cross-source sample name mapping (356 samples)
├── PRJNA590203_runinfo.csv     # Full SRA metadata
├── supplementary/              # Ottilie paper supplementary xlsx files
└── S288C_reference/            # Reference genome and annotations
    ├── S288C_R64.fa{,.fai}                 # Ensembl FASTA (chr: I-XVI, Mito)
    ├── S288C_R64.gff3                      # Ensembl GFF3 annotations
    ├── S288C_R64.gbff                      # NCBI GenBank (original NC_* names)
    ├── S288C_R64_ensembl_chrnames.gb       # GenBank with Ensembl chr names (for breseq)
    ├── chromosomes/                        # Per-chr FASTAs (for Control-FREEC)
    └── snpeff_cache/R64-1-1.105/           # Locally-built SnpEff cache
```

## Reference Genome

**Source**: S288C R64-1-1 from Ensembl release 105

**Why Ensembl?** Chromosome names (Roman numerals: I-XVI, Mito) must match the SnpEff `R64-1-1.105` database. NCBI uses `NC_*` accession-style names which cause mismatches.

**GenBank for breseq**: Downloaded from NCBI (has embedded sequences + rich annotations), then chromosome names sed-replaced to Ensembl convention via `rename_genbank_chromosomes.sh`.

**SnpEff cache**: Built locally because `snpeff.blob.core.windows.net` is unreachable from the Azure VM. Uses `snpEff build -gff3 -noCheckCds -noCheckProtein` inside the `quay.io/biocontainers/snpeff:5.2--hdfd78af_1` container.

All reference prep is captured in `prepare_s288c_reference.sh` (idempotent, skips existing files).

## Pilot Samples

| Sample | SRR | Role | Coverage |
|--------|-----|------|----------|
| NODRUG--GM2 | SRR10985539 | Parent (ancestor) | 53x |
| Doxorubicin-16--R2b | SRR10985527 | SNV benchmark (23 mutations) | 116x |
| Carmaphycin--R9-2 | SRR10985678 | SNV benchmark (15 mutations) | 213x |
| CBR110-15-R3a | SRR10985585 | CNV benchmark (ChrI aneuploidy) | 104x |

All paired-end 100bp reads (Illumina HiSeq 2500), haploid BY4741-derived strain.

## Pipeline Configuration

- **Tools**: HaplotypeCaller, breseq, CNVKit, Control-FREEC, SnpEff
- **Mode**: Joint germline (all status=0, ploidy=1)
- **Disabled**: baserecalibrator (no known-sites for S288C), FreeBayes (speed)
- **Profile**: `azureD4as,docker`

## Truth Set

From Ottilie et al. supplementary data:
- **Sup. Data 4**: 1,405 mutations (1,286 SNVs + 119 INDELs) across 363 clones
- **Sup. Data 5**: 24 CNVs (11 aneuploidies + 13 intrachromosomal amplifications)
- **Sup. Data 7**: 45 CRISPR/Cas9-validated causal alleles (biological validation)

## Known Issues

- `sra-tools 3.4.1` segfaults — pinned to 3.2.1 in `environment_data_retrieval.yml`
- Sample naming inconsistencies across supplementary tables and SRA (double-dash vs single-dash, abbreviations) — handled by `resolve_sra_accessions.py` with 3 manual overrides
