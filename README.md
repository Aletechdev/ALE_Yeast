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

## Background

This pipeline is built on nf-core-sarek 3.5.1. Modifications are documented in [SAREK_MODIFICATIONS.md](SAREK_MODIFICATIONS.md).

### Variant Calling Tools

| Tool | Type | Ploidy Support | Notes |
|------|------|----------------|-------|
| haplotypecaller | SNP & InDel | Custom ploidy | Preferred method for SNP & InDel |
| freebayes | SNP & InDel | Custom ploidy | |
| cnvkit | SV | Custom ploidy | |
| tiddit | SV | Custom ploidy | |
| manta | SV | Diploid only | Use breakpoints for cross validation |
| indexcov | CNV | - | Better for QC and coverage map |

---

## Input CSV Table

Adapted from nf-sarek (originally for human cancer research):

| Field | Description |
|-------|-------------|
| **experiment** | Experiment ID (maps to "patient" in Sarek) |
| **status** | `0` = ancestral strain (normal), `1` = evolved strain. Update: treat all samples as normal (0) to run haplotypecaller with `--joint_germline` |
| **ploidy** | Custom column for ploidy support |
| **fastq_1**, **fastq_2** | Path to FASTQ files (relative to where `nextflow` is run, or absolute path) |

**Requirement:** Each experiment **must have one normal sample** (status: 0)

**Example:**
```csv
experiment,sample,status,clonal_or_population,ploidy,lane,fastq_1,fastq_2
ALE_Exp1,A4-F5-I1-R1,0,clonal,2,L001,assets/reads/SubSampleA4-5_S11_L001_R1_001.fastq.gz,assets/reads/SubSampleA4-5_S11_L001_R2_001.fastq.gz
ALE_Exp1,A4-F5-I1-R1,0,clonal,2,L003,assets/reads/SubSampleA4-5_S11_L003_R1_001.fastq.gz,assets/reads/SubSampleA4-5_S11_L003_R2_001.fastq.gz
ALE_Exp1,A0-F0-I1-R1,0,clonal,2,L001,assets/reads/SubSampleCENPK113-7D-N_S53_L001_R1_001.fastq.gz,assets/reads/SubSampleCENPK113-7D-N_S53_L001_R2_001.fastq.gz
ALE_Exp1,A0-F0-I1-R1,0,clonal,2,L002,assets/reads/SubSampleCENPK113-7D-N_S53_L002_R1_001.fastq.gz,assets/reads/SubSampleCENPK113-7D-N_S53_L002_R2_001.fastq.gz
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