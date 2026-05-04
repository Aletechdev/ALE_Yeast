# Ottilie Xenobiotic ALE Benchmark

Benchmarking the NF_ALE Sarek pipeline against published variant calls from [Ottilie et al. (2022)](https://doi.org/10.1038/s42003-022-03076-7), a large-scale yeast ALE study with 363 drug-resistant clones.

## Tiered Benchmarking Strategy

| Tier | Samples | Purpose | Size | Status |
|------|---------|---------|------|--------|
| **1 — Pilot** | 4 (1 parent + 3 evolved) | Pipeline smoke test | ~4 GB | Complete |
| **2 — CRISPR + CNV** | 85 clones + parent | High-confidence SNV + CNV benchmark | ~40 GB | Planned |
| **3 — Full cohort** | 355 clones + parents | Comprehensive benchmark | ~170 GB | Future |

See [RESEARCH_CONTEXT.md](docs/RESEARCH_CONTEXT.md) for tier rationale and detailed science.

## Quick Start

```bash
# Prerequisites: conda activate nf-env, Docker running

# 1. Download truth set (supplementary xlsx files)
bash 01_data_retrieval/download_truth_set.sh

# 2. Prepare S288C reference genome + SnpEff cache
bash 02_reference_prep/prepare_s288c_reference.sh

# --- Tier 1: Pilot (4 samples) ---
bash 01_data_retrieval/download_pilot_fastq.sh
bash 03_pipeline/run_ottilie_pilot.sh

# --- Tier 2: CRISPR-validated (64 samples) ---
python 01_data_retrieval/select_tier2_crispr_validated.py  # generates clone list
bash 01_data_retrieval/download_all_fastq.sh               # download from SRA
# bash 03_pipeline/run_ottilie_tier2.sh                     # TODO
```

## Directory Structure

```
ottilie_xenobiotic_ale/
├── 01_data_retrieval/                    # SRA data download and sample resolution
│   ├── environment_data_retrieval.yml    # Conda env (sra-tools pinned to 3.2.1)
│   │
│   │  ── Step 1: Truth set ──
│   ├── download_truth_set.sh            # Download Sup 4/5/7 xlsx from PMC
│   │
│   │  ── Step 2: Sample resolution ──
│   ├── resolve_sra_accessions.py         # Build sample_name_dictionary.csv
│   ├── validate_dictionary.py            # QC: check dictionary completeness
│   ├── inspect_supplementary.py          # QC: explore supplementary data structure
│   │
│   │  ── Step 3: Tier selection ──
│   ├── select_tier2_crispr_validated.py  # Select 85 Tier 2 clones (CRISPR + CNV)
│   │
│   │  ── Step 4: FASTQ download ──
│   ├── download_pilot_fastq.sh          # Tier 1: 4 pilot samples
│   ├── download_tier2_fastq.sh          # Tier 2: 85 benchmark samples
│   ├── download_all_fastq.sh            # Tier 3: all 363 samples
│   └── subsample_fastq.sh              # Optional: subsample for quick testing
│
├── 02_reference_prep/                    # S288C R64-1-1 reference setup
│   ├── prepare_s288c_reference.sh        # Master script (all 5 steps, idempotent)
│   └── rename_genbank_chromosomes.sh     # NC_* -> Roman numeral chr names
│
├── 03_pipeline/                          # Sarek execution (customized nf-core/sarek 3.5.1)
│   ├── run_ottilie_pilot.sh              # Launch Tier 1 pilot benchmark
│   └── run_ottilie_pilot_subsampled.sh   # Launch Tier 1 with subsampled FASTQs
│
├── docs/                                 # Background documentation
│   ├── Nextflow_Pipeline_Benchmark_Project_Plan.md
│   └── RESEARCH_CONTEXT.md               # Full science context and tier rationale
│
└── README.md                             # This file
```

### Data Files (generated, not in this directory)

```
data/ottilie/
├── fastq/                                # Downloaded FASTQ files
├── samplesheet_pilot.csv                 # Sarek input — Tier 1 (4 pilot samples)
├── tier2_crispr_validated_clones.csv     # Tier 2 clone list (64 samples + metadata)
├── sample_name_dictionary.csv            # Cross-source sample name mapping (356 samples)
├── PRJNA590203_runinfo.csv               # Full SRA metadata
├── supplementary/                        # Ottilie paper supplementary xlsx files
│   ├── sup_4_*.xlsx                      # 1,405 mutations (SNV/INDEL truth set)
│   ├── sup_5_*.xlsx                      # 24 CNVs (CNV truth set)
│   └── sup_7_*.xlsx                      # CRISPR/Cas9 validation (45 confirmed)
└── S288C_reference/                      # Reference genome and annotations
    ├── S288C_R64.fa{,.fai}               # Ensembl FASTA (chr: I-XVI, Mito)
    ├── S288C_R64.gff3                    # Ensembl GFF3 annotations
    ├── S288C_R64.gbff                    # NCBI GenBank (original NC_* names)
    ├── S288C_R64_ensembl_chrnames.gb     # GenBank with Ensembl chr names (for breseq)
    ├── chromosomes/                      # Per-chr FASTAs (for Control-FREEC)
    └── snpeff_cache/R64-1-1.105/         # Locally-built SnpEff cache
```

## Reference Genome

**Source**: S288C R64-1-1 from Ensembl release 105

**Why Ensembl?** Chromosome names (Roman numerals: I-XVI, Mito) must match the SnpEff `R64-1-1.105` database. NCBI uses `NC_*` accession-style names which cause mismatches.

**GenBank for breseq**: Downloaded from NCBI (has embedded sequences + rich annotations), then chromosome names sed-replaced to Ensembl convention via `rename_genbank_chromosomes.sh`.

**SnpEff cache**: Built locally using `snpEff build -gff3 -noCheckCds -noCheckProtein` inside the `quay.io/biocontainers/snpeff:5.2--hdfd78af_1` container. This avoids dependency on the remote SnpEff download server, which may be unreachable from some HPC environments.

All reference prep is captured in `prepare_s288c_reference.sh` (idempotent, skips existing files).

## Tier 1 — Pilot Samples

| Sample | SRR | Role | Coverage |
|--------|-----|------|----------|
| NODRUG--GM2 | SRR10985539 | Parent (ancestor) | 53x |
| Doxorubicin-16--R2b | SRR10985527 | SNV benchmark (23 mutations) | 116x |
| Carmaphycin--R9-2 | SRR10985678 | SNV benchmark (15 mutations) | 213x |
| CBR110-15-R3a | SRR10985585 | CNV benchmark (ChrI aneuploidy) | 104x |

All paired-end 100bp reads (Illumina HiSeq 2500), haploid BY4741-derived strain.

## Tier 2 — CRISPR-Validated + CNV Clones

**85 clones** (64 CRISPR-validated + 21 CNV-only), combining the two highest-confidence subsets.

**Selection logic** (`01_data_retrieval/select_tier2_crispr_validated.py`):
1. Parse 68 CRISPR-validated mutations from Sup 7 (gene + amino acid change)
2. Match against Sup 4 clones (converting single-letter → three-letter AA codes)
3. 48/68 mutations matched → 65 unique clones (64 with SRR accessions)
4. Add 21 Sup 5 CNV clones not already in step 3 (all have SRR accessions)
5. Cross-reference with `sample_name_dictionary.csv` for download accessions

**SNV coverage**: 41 compounds, 37 genes, 48 CRISPR-validated mutations. Includes YRR1 (most frequently mutated), ERG9/ERG12/ERG20 (ergosterol pathway), ACT1 (actin), TUB2 (tubulin), TOP2 (topoisomerase).

**CNV coverage**: 23 clones with 24 CNV events (11 aneuploidies + 13 amplifications) for benchmarking CNVKit and Control-FREEC. 2 of these overlap with the CRISPR set, 21 are CNV-only additions.

**Output**: `data/ottilie/tier2_crispr_validated_clones.csv`

## Pipeline Configuration

This benchmark uses a **customized fork of nf-core/sarek 3.5.1** with ALE-specific modifications (ploidy support, breseq integration, AF-based somatic filtering, joint germline filter annotation fallback, etc.). A next version release is in progress.

- **Tools**: HaplotypeCaller, breseq, CNVKit, Control-FREEC, SnpEff
- **Mode**: Joint germline (all status=0, ploidy=1)
- **Disabled**: baserecalibrator (no known-sites for S288C), FreeBayes (speed)
- **Profile**: Adjust to your environment (e.g., `singularity,slurm` for HPC, `docker` for local)

## Resource Estimates

Based on Tier 1 actual measurements (4 samples on a 4 vCPU / 16 GB RAM node).

### Per-Tier Storage

| Tier | FASTQs | Work Dir | Output | Total | Temp (fasterq-dump) |
|------|--------|----------|--------|-------|---------------------|
| **1 — Pilot** (4 samples) | 4 GB | 36 GB | 3 GB | **43 GB** | ~12 GB peak |
| **2 — CRISPR+CNV** (86 samples) | ~40 GB | ~770 GB | ~66 GB | **~876 GB** | ~120 GB peak |
| **3 — Full cohort** (363 samples) | ~170 GB | ~3.3 TB | ~280 GB | **~3.7 TB** | ~500 GB peak |

Work dir estimate: ~9 GB/sample (Tier 1 actual: 36 GB / 4 samples).
fasterq-dump temp: ~3× compressed FASTQ size (uncompressed intermediate before gzip).

### Peak RAM by Process (Tier 1 Actual)

| Process | Peak RSS | Scaling | Tier 2 Estimate |
|---------|----------|---------|-----------------|
| GATK4_MarkDuplicates | 8.9 GB | Per sample (constant) | 8.9 GB |
| breseq | 5.7 GB | Per sample (constant) | 5.7 GB |
| BWA-MEM | 4.8 GB | Per sample (constant) | 4.8 GB |
| GATK4_HaplotypeCaller | 2.5 GB | Per sample (constant) | 2.5 GB |
| SnpEff | 2.4 GB | Per sample (constant) | 2.4 GB |
| GATK4_GenotypegVCFs | 975 MB | JVM heap capped by `-Xmx` | ~2-4 GB |
| GATK4_GenomicsDBImport | 381 MB | JVM heap capped by `-Xmx` | ~1-2 GB |
| MultiQC | 995 MB | Scales with samples | ~2-4 GB |
| CNVKit_BATCH | 719 MB | Per sample (constant) | 719 MB |
| Control-FREEC | 18 MB | Per sample (constant) | 18 MB |

**RAM is not a limiting factor** for yeast (12 Mb genome). GATK joint calling heap is capped by `-Xmx` (derived from `task.memory`). Standard HPC nodes (16+ GB) are sufficient for all tiers.

### Runtime Estimates (single node, 4 CPU, serial)

| Process | Per Sample | 86 Samples (serial) | Notes |
|---------|-----------|---------------------|-------|
| BWA-MEM | ~5 min | ~7 hrs | Parallelizable |
| MarkDuplicates | ~3 min | ~4 hrs | Parallelizable |
| HaplotypeCaller | ~8 min | ~11 hrs | Parallelizable |
| **breseq** | **~2 hrs** | **~172 hrs (7 days)** | **Bottleneck** — consider disabling for Tier 2 |
| CNVKit | ~2 min | ~3 hrs | Parallelizable |
| Control-FREEC | ~1 min | ~1.5 hrs | Parallelizable |
| Joint calling | ~30 sec | ~5 min | Single job, all samples |

**Total estimate (single node, serial)**: ~2-3 days without breseq, **~8-10 days with breseq**.

### Feasibility by Tier

| | Tier 1 (4 samples) | Tier 2 (86 samples) | Tier 3 (363 samples) |
|--|---------------------|---------------------|----------------------|
| **Disk** | ~43 GB | **~876 GB** | **~3.7 TB** |
| **RAM** | 9 GB peak | 16 GB sufficient | 16 GB sufficient |
| **Runtime (4 CPU, serial)** | ~8 hrs | ~8–10 days | ~5–6 weeks |
| **Runtime (HPC, parallel)** | <1 hr | ~6–12 hrs | ~1–2 days |

**Tier 1** runs comfortably on a single workstation or laptop (4+ cores, 16 GB RAM, 50 GB disk).

**Tier 2 and Tier 3 should be run on an HPC cluster or cloud compute**, not a local workstation:
- Work directory alone requires ~770 GB (Tier 2) or ~3.3 TB (Tier 3)
- breseq is the runtime bottleneck (~2 hrs/sample, serial) — parallelization across nodes is essential
- Nextflow natively supports SLURM, PBS, LSF, and cloud executors — set your profile accordingly

**Recommended workflow:**
1. Download FASTQs to a shared filesystem (scratch/project space)
2. Run pipeline with an HPC executor profile (e.g., `nextflow run ... -profile singularity,slurm`)
3. Use `--max_memory`, `--max_cpus`, `--max_time` to match your cluster's queue limits

## Truth Set

From Ottilie et al. supplementary data (downloaded via `01_data_retrieval/download_truth_set.sh`):
- **Sup. Data 4**: 1,405 mutations (1,286 SNVs + 119 INDELs) across 355 clones
- **Sup. Data 5**: 24 CNVs (11 aneuploidies + 13 intrachromosomal amplifications) across 23 clones
- **Sup. Data 7**: 45 CRISPR/Cas9-validated causal alleles across 37 genes — used to select Tier 2

## Known Issues

- `sra-tools 3.4.1` segfaults — pinned to 3.2.1 in `environment_data_retrieval.yml`
- Sample naming inconsistencies across supplementary tables and SRA (double-dash vs single-dash, abbreviations) — handled by `resolve_sra_accessions.py` with 3 manual overrides
- 1 Tier 2 CRISPR clone (EAW901 / DDD01035522--1R2a) has no SRR accession in the dictionary
- **breseq is the runtime bottleneck** — ~2 hrs/sample serial. Consider disabling for Tier 2 initial run, or running on cloud with parallelism
- **Joint calling**: GATK heap is JVM-capped (`-Xmx`), not a concern for yeast genome size
