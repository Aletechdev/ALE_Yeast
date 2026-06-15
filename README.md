# ALE Nextflow Pipeline

A variant calling pipeline for Adaptive Laboratory Evolution (ALE) experiments, built on nf-core/sarek 3.5.1.

Install NextFlow using conda: https://www.nextflow.io/docs/latest/install.html#conda
Install docker: https://docs.docker.com/engine/install/

## Run Environment

This pipeline is recommended to run on x86_64 systems. Some GATK processes do not support Apple Silicon. An Azure VM of D4as type is used for development.

## Quick Start

```bash
git clone git@github.com:Aletechdev/ALE_Yeast.git
cd ALE_Yeast
bash bin/test_nf.sh
```

## Test Dataset (`bin/test_nf.sh`)

The test script runs the full pipeline on a small bundled dataset for development and validation.

### Test data

All test data is included in the repo under `assets/`:

| Component | Path | Size | Description |
|-----------|------|------|-------------|
| Reads | `assets/reads/` | ~4 MB | 5 subsampled yeast samples (4 lanes each) |
| Reference | `assets/references/draft_ref52.fasta` | ~114 MB | CEN.PK yeast reference genome |
| SnpEff cache | `assets/references/snpeff_cache/` | (included) | Pre-built annotation cache (`draft_ref.52`) |
| Samplesheet | `assets/reads/samplesheet.csv` | — | 5-sample input table |

**Samples in test set:**

| Sample | Type | Ploidy | Description |
|--------|------|--------|-------------|
| A0-F0-I1-R1 | Clonal | 1 | Ancestral strain (haploid) |
| A1-F6-I1-R1 | Clonal | 1 | Evolved clone (haploid) |
| A6-F6-I1-R1 | Clonal | 1 | Evolved clone (haploid) |
| A1-F6-I2-R1 | Population | 2 | Spore seq POS (diploid) |
| A1-F6-I3-R1 | Population | 2 | Spore seq NEG (diploid) |

**Generating the samplesheet:**

```bash
python bin/prepare_input/generate_sarek_csv_subsample.py
```

This script scans `assets/reads/` for `SubSample*.fastq.gz` files and generates the samplesheet. Sample metadata (name mapping, status, ploidy, clonal/population) is configured via maps at the top of the script.

### Tools enabled in test

The test script enables: `snpeff`, `haplotypecaller`, `freebayes`, `cnvkit`, `tiddit`, `manta`

With flags: `--joint_germline`, `--split_haplotypecaller_joint_vcf`, `--hard_filter_haplotypecaller_joint`

Note: `mutect2` and `joint_mutect2` are **not** included in the test profile (used in production only via `bin/CENPK_run_sarek_351.sh`).

### Output

Results go to `output_test_001/`, work directory to `work_test_001/`. The script uses `-resume` so re-runs skip completed steps.

### Test vs Production

| | Test (`bin/test_nf.sh`) | Production (`bin/CENPK_run_sarek_351.sh`) |
|---|---|---|
| Data | `assets/reads/` (~4 MB subsampled) | Full-size FASTQs (not in repo) |
| Samples | 5 | 17+ (7 bulk + 10 spore seq) |
| Tools | No mutect2 | mutect2 + joint_mutect2 |
| Reference | `assets/references/` | `data/BakerYeast_reference/` |
| Output | `output_test_001/` | `output/` |

### Development workflow

```bash
# First run (full pipeline)
bash bin/test_nf.sh

# After modifying pipeline code, re-run (resumes from cache)
bash bin/test_nf.sh

# Clean work directory to force re-run from scratch
rm -rf work_test_001
bash bin/test_nf.sh

# Check what ran
cat output_test_001/pipeline_info/execution_report_*.html
```

## Background

This pipeline is built on nf-core-sarek 3.5.1. Modifications are documented in [SAREK_MODIFICATIONS.md](SAREK_MODIFICATIONS.md).

### Variant Calling Tools

| Tool | Type | Ploidy Support | Notes |
|------|------|----------------|-------|
| haplotypecaller | SNP & InDel | Custom ploidy | Preferred method for SNP & InDel |
| freebayes | SNP & InDel | Custom ploidy | |
| cnvkit | SV | Diploid baseline | `--ploidy` removed; log2 ratios are reference-relative. See [cnvkit_ploidy_cn_scale.md](docs/variant-calling/cnvkit/cnvkit_ploidy_cn_scale.md) |
| tiddit | SV | Custom ploidy (`-n`) | Affects coverage normalization and DUP/DEL GT thresholds; GT always diploid notation. See [tiddit_ploidy_behavior.md](docs/variant-calling/tiddit/tiddit_ploidy_behavior.md) |
| manta | SV | Diploid only | Use breakpoints for cross validation |
| indexcov | CNV | - | Better for QC and coverage map |

---

## Input CSV Table

Adapted from nf-sarek (originally for human cancer research):

| Field | Description |
|-------|-------------|
| **experiment** | Experiment ID (maps to "patient" in Sarek) |
| **sample** | Sample ID in standardized ALE format (e.g., `A1-F6-I1-R1`) |
| **status** | `0` = normal. Treat all samples as normal (0) to run haplotypecaller with `--joint_germline` |
| **clonal_or_population** | `clonal` for bulk sequencing, `population` for spore seq |
| **ploidy** | Sample ploidy (1 = haploid, 2 = diploid) |
| **sex** | `XX` for yeast (required by Sarek for Control-FREEC) |
| **lane** | Sequencing lane (e.g., `L001`) |
| **fastq_1**, **fastq_2** | Path to FASTQ files (relative to where `nextflow` is run, or absolute path) |

**Requirement:** Each experiment **must have one normal sample** (status: 0)

**Example:**
```csv
experiment,sample,status,clonal_or_population,ploidy,sex,lane,fastq_1,fastq_2
ALE_Exp1,A0-F0-I1-R1,0,clonal,1,XX,L001,assets/reads/SubSampleCENPK113-7D-N_S53_L001_R1_001.fastq.gz,assets/reads/SubSampleCENPK113-7D-N_S53_L001_R2_001.fastq.gz
ALE_Exp1,A1-F6-I1-R1,0,clonal,1,XX,L001,assets/reads/SubSampleA1-6_S2_L001_R1_001.fastq.gz,assets/reads/SubSampleA1-6_S2_L001_R2_001.fastq.gz
ALE_Exp1,A1-F6-I2-R1,0,population,2,XX,L001,assets/reads/SubSampleSp-A1-6-POS_S61_L001_R1_001.fastq.gz,assets/reads/SubSampleSp-A1-6-POS_S61_L001_R2_001.fastq.gz
```

---

## Process GenBank to Generate Reference Files

This script processes GenBank files to generate all required reference files for the pipeline:
- Reference genome FASTA (`--fasta`)
- SnpEff annotation cache (`--snpeff_cache`)
- SnpEff database name (`--snpeff_db`)

**Script location:** `bin/prepare_input/process_GeneBank/process_genbank_auto.sh`

### Usage

```bash
./process_genbank_auto.sh <input.gbk> [output_dir]
```

**Arguments:**
- `input.gbk` - Input GenBank file (.gbk or .gb)
- `output_dir` - Output directory (optional, default: ./genbank_processed)

### What It Does

1. Extracts organism information from GenBank file
2. Converts GenBank to FASTA (reference genome)
3. Converts GenBank to GFF3 (annotations)
4. Generates SnpEff cache for variant annotation
5. Creates a processing summary

### Example with Ogataea polymorpha

```bash
# Process the included GenBank file
./bin/prepare_input/process_GeneBank/process_genbank_auto.sh \
    assets/genebank/Ogataea_polymorpha_NCYC495.gbk \
    assets/genebank/processed

# The script outputs the exact parameters to use:
# ==============================================
# Pipeline parameters to use:
# ==============================================
# --fasta        assets/genebank/processed/ogataea_polymorpha.fasta
# --snpeff_cache assets/genebank/processed/snpeff_cache
# --snpeff_db    ogataea_polymorpha
# ==============================================
```

### How `--snpeff_db` is Determined

The `--snpeff_db` value is the **genome name** derived from the organism name in the GenBank file:

| Step | Value |
|------|-------|
| GenBank `ORGANISM` field | `Ogataea polymorpha` |
| Converted to | `ogataea_polymorpha` (lowercase, spaces → underscores) |
| Matches subdirectory | `snpeff_cache/ogataea_polymorpha/` |

You can find this value in `organism_info.sh` after processing:
```bash
cat assets/genebank/processed/organism_info.sh
# GENOME_NAME="ogataea_polymorpha"  <-- use this for --snpeff_db
```

### Output Structure and Pipeline Parameters

```
assets/genebank/processed/
├── organism_info.sh              # Contains GENOME_NAME for --snpeff_db
├── ogataea_polymorpha.fasta      # --fasta <path to this file>
├── ogataea_polymorpha.gff3       # Annotation GFF3 (1.4 MB)
├── snpeff_cache/                 # --snpeff_cache <path to this directory>
│   ├── ogataea_polymorpha/       # --snpeff_db <this subdirectory name>
│   └── data/ogataea_polymorpha/  # SnpEff data directory
└── PROCESSING_SUMMARY.md         # Processing summary
```

> **Note:** Only the GenBank file (`Ogataea_polymorpha_NCYC495.gbk`) is stored in git. The processed files are generated locally by running the script.

### Requirements

- Docker (for any2fasta and snpEff containers)
- Bash 4+


---

## Running with Different Projects

Organize data in project-specific folders while sharing the pipeline code:

### 1. Create a project folder

```bash
mkdir -p ~/projects/my_ale_experiment
cd ~/projects/my_ale_experiment
```

### 2. Create a symbolic link to the pipeline

```bash
ln -s /path/to/ALE_nextflow pipeline
```

### 3. Organize your project data

```
my_ale_experiment/
├── pipeline -> /path/to/ALE_nextflow    # Symlink to pipeline
├── data/
│   ├── reads/                           # Your FASTQ files
│   └── references/                      # Processed GenBank output
├── samplesheet.csv                      # Your input CSV
└── output/                              # Pipeline results
```

### 4. Run the pipeline

```bash
nextflow run ./pipeline/nf-core-sarek_3.5.1/3_5_1/main.nf \
    -profile azureD4as,docker \
    -w ./work \
    --input samplesheet.csv \
    --outdir ./output \
    --fasta ./data/references/organism_name.fasta \
    --snpeff_cache ./data/references/snpeff_cache \
    --snpeff_db organism_name \
    --genome null --igenomes_ignore \
    --skip_tools baserecalibrator \
    --tools snpeff,haplotypecaller \
    --joint_germline
```

This approach keeps your data separate from the pipeline code, making it easy to:
- Update the pipeline independently
- Run multiple projects with different datasets
- Track pipeline version per project

---

## Seqera Platform Deployment (Azure)

This section documents running the pipeline on Seqera Platform with Azure Batch compute.

### Files Prepared

| File | Purpose |
|------|---------|
| `conf/seqera_azure.config` | Nextflow config (resource limits, retry strategy, Docker) |
| `conf/params_seqera_test.yml` | Launch parameters for Seqera Platform |
| `assets/reads/samplesheet_azure.csv` | Samplesheet with `az://` blob paths |
| `bin/upload_test_data_azure.sh` | Upload script for test data to Azure Blob |

### Upload Test Data

```bash
export STORAGE_ACCOUNT="your-storage-account-name"
bash bin/upload_test_data_azure.sh
```

This uploads to container `aletest`:
- `az://aletest/assets/reads/` - FASTQ files + samplesheet
- `az://aletest/assets/references/` - FASTA, GFF3, SnpEff cache

### Seqera Launch Configuration

1. **Compute Environment**: Azure Batch (configured in Seqera Platform)
2. **Config profiles**: `docker`
3. **Nextflow config**: Paste content of `conf/seqera_azure.config`
4. **Pipeline parameters**: Upload `conf/params_seqera_test.yml`

### breseq Reference Format Limitation

⚠️ **Current limitation**: breseq is configured with GFF3 reference (`draft_ref52.gff3`) instead of GenBank format.

**Impact**:
- breseq runs successfully with GFF3
- Reduced annotation quality in breseq HTML reports
- GenomeDiff → VCF conversion works normally

**Recommendation**: For production use, provide a GenBank (.gb/.gbk) file for full breseq annotation support.

### TODO: Public Test Dataset

The current test dataset uses proprietary yeast data. For public demos and CI/CD, we need:

- [ ] **Public reference genome** with GenBank file (e.g., S. cerevisiae S288C from NCBI)
- [ ] **Public FASTQ data** from SRA/ENA (e.g., yeast ALE experiment reads)
- [ ] **Minimal samplesheet** (2-3 samples for fast testing)

**Candidate public datasets**:
- *S. cerevisiae* S288C: [GCF_000146045.2](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000146045.2/) (GenBank available)
- *E. coli* K-12 MG1655: [GCF_000005845.2](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000005845.2/) (well-annotated, common ALE organism)
- SRA ALE datasets: Search "adaptive laboratory evolution" on SRA for paired-end Illumina reads