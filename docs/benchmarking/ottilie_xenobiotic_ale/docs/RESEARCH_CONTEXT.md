# Ottilie et al. (2022) — Research Context

## Reference

Ottilie et al., "Adaptive laboratory evolution in S. cerevisiae highlights role of transcription factors in fungal xenobiotic resistance", Communications Biology 5:128 (2022)
- DOI: https://doi.org/10.1038/s42003-022-03076-7
- PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC8837787/
- BioProject: [PRJNA590203](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA590203)

---

## Study Design

### Strain Background
- **Organism**: *Saccharomyces cerevisiae* ABC16-Green Monster (GM) strain
- **Genetic background**: S288C-derived (BY4741)
- **Engineering**: 16 ABC transporter genes replaced with GFP cassettes
- **Rationale**: Removing ABC transporters lowers effective drug dose needed for selection, enabling drug target identification at physiologically relevant concentrations
- **NOT CEN.PK** — different from our current pipeline reference

### Selection Protocol
- **Compound screen**: ~1,600 compounds screened at IC50, 80 yielded resistant clones
- **Starting culture**: ~500,000 cells from a single colony
- **Growth conditions**: 20 mL YPD media, grown to saturation (OD600 1.0-1.5) at compound IC50
- **Passaging**: Serial transfer to fresh media with increasing compound concentrations
- **Generations**: ~14 per dilution cycle, 5-20 days per cycle
- **Resistance cycles**: Average 2.93 (range 1-9)
- **Resistance criteria**: Growth at 2-3x above IC50 AND >=1.5-fold IC50 shift vs parental
- **Yield**: 355 resistant clones from 80 compounds; up to 12 independent selections per compound

### Sequencing
- **Samples**: 363 sequenced (355 resistant + 8 parent/control)
- **Library prep**: Illumina Nextera XT, 200 ng genomic DNA, standard dual indexing
- **Platform**: Illumina HiSeq 2500 RapidRun mode
- **Read type**: Paired-end, minimum 100 bp
- **Coverage**: Average 54.6x
- **Mapping rate**: 99.7% to reference

---

## Variant Calling (Paper's Methods)

### SNV/INDEL Pipeline
- **Aligner**: BWA-mem to S288C R64-1-1
- **Preprocessing**: Picard Tools (MarkDuplicates, etc.)
- **Variant caller**: GATK HaplotypeCaller
- **Filtering**: GATK recommended hard filters
- **Annotation**: SnpEff v4.3 + SGD metadata
- **Parent subtraction**: Custom script removing variants shared between parent and evolved clones
- **Total mutations**: 1,405 (1,286 SNVs + 119 INDELs); average 3.96 per clone

### CNV Pipeline
- **Tool**: GATK DiagnoseTargets (read coverage across defined gene intervals)
- **Processing**: Coverage values log-transformed, then mean-centered
- **Filtering**: Retained if >=2-3x fold coverage change vs parent AND spanning >=4 genes
- **Results**: 24 CNVs (11 aneuploidy events across 10 clones + 13 intrachromosomal amplifications)

### Reference Genome Versions

| Version | Purpose | Source |
|---------|---------|--------|
| **R64-1-1** | BWA-mem alignment, SNV/INDEL calling, CNV detection | Ensembl / SGD |
| **R64-2-1** | Intergenic mutation annotation only (GFF from SGD) | SGD |

All read alignment was to **R64-1-1** — this is the version we use for benchmarking.

---

## Key Biological Findings

### YRR1/YRM1 Transcription Factor Dominance
- Two Zn2C6 transcription factors mutated **100 times** across **19 structurally diverse compounds** (p < 1e-100 enrichment)
- All resistance mutations clustered in a ~170 amino acid C-terminal domain
- **Gain-of-function**: RT-qPCR showed 1.5-140-fold higher mRNA levels of target genes
- **Cross-resistance**: YRR1-mutant clones showed strong cross-resistance regardless of chemical structure

### CRISPR/Cas9 Validation
- 61 alleles tested via CRISPR engineering in ABC16-GM strain
- **45 confirmed causal** across 37 genes
- Independently mutated genes had high probability of confirming resistance

---

## Truth Set

Downloaded via `01_data_retrieval/truth_set/download_truth_set.sh` into `data/ottilie/supplementary/`.

| Supplementary | Description | Records | URL |
|---|---|---|---|
| **Data 4** | SNV/INDEL mutations across 355 clones | 1,405 (1,286 SNVs + 119 INDELs) | [MOESM6](https://pmc.ncbi.nlm.nih.gov/articles/instance/8837787/bin/42003_2022_3076_MOESM6_ESM.xlsx) |
| **Data 5** | CNV events across 23 clones | 24 (11 aneuploidies + 13 amplifications) | [MOESM7](https://pmc.ncbi.nlm.nih.gov/articles/instance/8837787/bin/42003_2022_3076_MOESM7_ESM.xlsx) |
| **Data 7** | CRISPR/Cas9 validation | 61 tested, 45 confirmed causal | [MOESM9](https://pmc.ncbi.nlm.nih.gov/articles/instance/8837787/bin/42003_2022_3076_MOESM9_ESM.xlsx) |

### How the Truth Sets Relate

- **Data 4** is the primary SNV/INDEL truth set for precision/recall benchmarking
- **Data 5** is the CNV truth set; events defined by >=2-3x coverage change spanning >=4 genes
- **Data 7** contains CRISPR-engineered validation clones (new EAW IDs) — they don't have SRA data themselves, but 48 of 68 validated mutations can be traced back to 65 original evolved clones in Sup 4

---

## Tiered Benchmarking Rationale

### Why Tiers?

The full dataset (363 clones, ~170 GB FASTQ) is too large for iterative development. Tiers allow validating the pipeline incrementally:

1. **Tier 1 (Pilot)**: Verify end-to-end execution on yeast data, catch configuration issues early
2. **Tier 2 (CRISPR + CNV)**: High-confidence benchmark — CRISPR validation provides ground truth independent of bioinformatics methods
3. **Tier 3 (Full cohort)**: Comprehensive statistics, scalability validation on cloud/HPC

### Tier 2 Selection Logic

**85 clones** = 64 CRISPR-validated + 21 CNV-only (implemented in `select_tier2_crispr_validated.py`)

**CRISPR-validated clones (64 with SRR accessions):**
1. Parse 68 CRISPR-validated mutations from Sup 7 (gene + amino acid change)
2. Match against Sup 4 clones (converting single-letter to three-letter AA codes)
3. 48/68 mutations matched → 65 unique clones (64 with SRR accessions)
4. Covers 41 compounds, 37 genes, including YRR1, ERG9/ERG12/ERG20, ACT1, TUB2, TOP2

**CNV-only clones (21 additions from Sup 5):**
- Without these, Tier 2 would have only 2 CNV events — insufficient for tool benchmarking
- Adds 21 CNV events (aneuploidies + intrachromosomal amplifications)
- All 21 have SRR accessions in the sample dictionary

**Combined Tier 2 benchmarks:**
1. **SNV Recall**: Do we detect all 48 CRISPR-validated mutations?
2. **SNV Precision**: How many of our calls match Sup 4?
3. **CNV Sensitivity**: Do CNVKit/Control-FREEC detect all 24 CNV events across 23 clones?

### Cross-Referencing Sup 7 → Sup 4

Sup 7 EAW clone IDs are CRISPR-engineered strains, not the original sequenced clones. The validated *mutations* (gene + AA change) are matched back to Sup 4 clones:

- **48/68** mutations match a Sup 4 clone (same gene + AA change)
- **20/68** unmatched — likely from 23 previously published selections (SRX1745463-SRX1869282) not in PRJNA590203
- **64 of 65** matched clones have SRR accessions (1 missing: EAW901)

---

## Differences from Current Pipeline (CEN.PK / Pereira)

| Feature | Pereira (current) | Ottilie (benchmark) |
|---------|-------------------|---------------------|
| Strain | CEN.PK113-7D | ABC16-GM (S288C background) |
| Reference | draft_ref52 (custom) | S288C R64-1-1 (standard) |
| Samples | 17 (7 clonal + 10 spore-seq) | 363 clones |
| Truth set | 24 SNVs (Table S8) | 1,405 variants + 45 CRISPR-validated |
| Selection | Adipic acid tolerance | 80 different xenobiotics |
| Ploidy | Haploid/Diploid | Haploid (GM strain) |

### Implications for Pipeline
- Standard S288C reference = no custom cache issues, easier comparison with published tools
- Larger sample set = more robust benchmarking statistics
- CRISPR-validated subset provides ground truth independent of calling methodology
- CNV benchmarking feasible: our CNVKit + Control-FREEC vs paper's GATK DiagnoseTargets
