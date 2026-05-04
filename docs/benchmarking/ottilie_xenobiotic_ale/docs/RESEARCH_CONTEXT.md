# Ottilie et al. Benchmark Study Context

## Reference
Ottilie et al., "Adaptive laboratory evolution in S. cerevisiae highlights role of transcription factors in fungal xenobiotic resistance", Communications Biology 5:128 (2022)
- PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC8837787/
- DOI: https://www.nature.com/articles/s42003-022-03076-7

## Study Design

### Strain Background
- **Organism**: *Saccharomyces cerevisiae* ABC16-Green Monster (GM) strain
- **Genetic background**: S288C-derived (BY4741)
- **Engineering**: 16 ABC transporter genes replaced with GFP cassettes
- **Rationale**: Wild-type yeast requires high compound concentrations due to drug export pumps; removing ABC transporters lowers the effective dose needed for in vitro selection, enabling drug target identification at physiologically relevant concentrations
- **NOT CEN.PK** — different from our current pipeline reference

### Selection Protocol
- **Compound screen**: ~1,600 compounds screened at IC50, 80 yielded resistant clones
- **Starting culture**: ~500,000 cells from a single colony
- **Growth conditions**: 20 mL YPD media, grown to saturation (OD600 1.0–1.5) at compound IC50
- **Passaging**: Serial transfer to fresh media with increasing compound concentrations
- **Generations**: ~14 generations per dilution cycle, 5–20 days per cycle
- **Resistance cycles**: Average 2.93 (range 1–9)
- **Resistance criteria**: (1) growth at 2–3× above IC50, AND (2) ≥1.5-fold IC50 shift vs parental line
- **Yield**: 355 resistant clones from 80 compounds; up to 12 independent selections per compound

## Reference Genome Versions

| Version | Purpose | Source |
|---------|---------|--------|
| **R64-1-1** | BWA-mem alignment, SNV/INDEL calling, CNV detection | Ensembl / SGD |
| **R64-2-1** | Intergenic mutation annotation only (GFF from SGD) | SGD |

- All read alignment was to **R64-1-1** — this is the version we use for benchmarking
- CNV detection (GATK DiagnoseTargets) operated on the same R64-1-1 alignment files
- R64-2-1 was used only for a downstream Python script mapping 271 intergenic mutations to chromosomal features

## Sequencing Data
- **Samples**: 363 evolved clones sequenced (355 resistant + 8 parent/control)
- **Library prep**: Illumina Nextera XT kit, 200 ng genomic DNA, standard dual indexing
- **Platform**: Illumina HiSeq 2500 RapidRun mode
- **Read type**: Paired-end, minimum 100 bp
- **Coverage**: Average 54.6×
- **Mapping rate**: 99.7% to reference
- **BioProject**: PRJNA590203
- **Additional SRA**: SRX1745463-SRX1869282 (23 previously published selections)

## Variant Calling (Paper's Methods)

### SNV/INDEL Pipeline
- **Aligner**: BWA-mem → R64-1-1
- **Preprocessing**: Picard Tools (MarkDuplicates, etc.)
- **Variant caller**: GATK HaplotypeCaller
- **Filtering**: GATK recommended hard filters
- **Annotation**: SnpEff database built from R64-1-1 GFF ("to leave only high-quality variants with high allelic depth")
- **Parent subtraction**: Custom shell script removing variants shared between parent and evolved clones (only mutations arising during selection are retained)
- **Total mutations**: 1,405 (1,286 SNVs + 119 INDELs); average 3.96 per clone

### CNV Pipeline
- **Tool**: GATK DiagnoseTargets (read coverage across defined gene intervals)
- **Processing**: Coverage values log-transformed, then mean-centered across and within arrays (Cluster)
- **Filtering**: Retained if ≥2–3× fold coverage change vs parent AND spanning ≥4 genes
- **Results**: 24 CNVs (11 aneuploidy events across 10 clones + 13 intrachromosomal amplifications)

## Key Biological Findings

### YRR1/YRM1 Transcription Factor Dominance
- Two Zn₂C₆ transcription factors (YRR1 and YRM1) mutated **100 times** across **19 structurally diverse compounds** (p < 1 × 10⁻¹⁰⁰ enrichment)
- All resistance-conferring mutations clustered in a **~170 amino acid C-terminal domain**, distal to the DNA-binding domain
- **Gain-of-function mechanism**: RT-qPCR showed 1.5–140-fold higher mRNA levels of YRR1, SNG1, FLG1, and AZR1 in evolved mutants vs wild-type
- **Cross-resistance**: YRR1-mutant clones showed strong cross-resistance to all tested compounds regardless of chemical structure

### CRISPR/Cas9 Validation
- **Selection criteria**: Mutations chosen by frequency of occurrence and/or gene product implicated as potential drug target
- **Method**: CRISPR/Cas9 genome engineering in ABC16-GM strain using gene-specific gRNA + synthesized donor template (IDT), lithium acetate transformation
- **Results**: 61 alleles tested → **45 confirmed causal** across 37 genes
- Independently mutated genes had high probability of confirming at least partial resistance

## Truth Set / Validation Data

Downloaded via `01_data_retrieval/download_truth_set.sh` into `data/ottilie/supplementary/`.

| Supplementary | Description | File | URL |
|---|---|---|---|
| **Data 4** | 1,405 mutations (1,286 SNVs + 119 INDELs) across 363 clones | `sup_4_*.xlsx` | [MOESM6](https://pmc.ncbi.nlm.nih.gov/articles/instance/8837787/bin/42003_2022_3076_MOESM6_ESM.xlsx) |
| **Data 5** | 24 CNVs (11 aneuploidies + 13 intrachromosomal amplifications) | `sup_5_*.xlsx` | [MOESM7](https://pmc.ncbi.nlm.nih.gov/articles/instance/8837787/bin/42003_2022_3076_MOESM7_ESM.xlsx) |
| **Data 7** | CRISPR/Cas9 validation (61 tested, 45 confirmed causal) | `sup_7_*.xlsx` | [MOESM9](https://pmc.ncbi.nlm.nih.gov/articles/instance/8837787/bin/42003_2022_3076_MOESM9_ESM.xlsx) |

- **Data 4** is the primary SNV/INDEL truth set for precision/recall benchmarking
- **Data 5** is the CNV truth set; filtered for ≥2-3× fold coverage change vs parent and spanning ≥4 genes
- **Data 7** is biological validation — CRISPR-engineered clones (new EAW IDs) with no SRA data of their own, but 48 of 68 validated mutations can be traced back to 65 original evolved clones in Sup 4

### Cross-Referencing Supplementary Data

Sup 7 EAW clone IDs are mostly CRISPR-engineered strains created for validation, not
the original sequenced clones. They do not have SRA sequencing data. However, the
validated *mutations* (gene + amino acid change) can be matched back to Sup 4 clones
that carry those exact variants:

- **48/68** CRISPR-validated mutations match a Sup 4 clone (same gene + AA change)
- **20/68** unmatched — likely from the 23 previously published selections (SRX1745463–SRX1869282) not in the main PRJNA590203 dataset
- **65 unique Sup 4 clones** carry at least one CRISPR-validated mutation
- **64 of 65** have SRR accessions in the sample dictionary (1 missing: EAW901)

Selection logic: `01_data_retrieval/select_tier2_crispr_validated.py`
Output: `data/ottilie/tier2_crispr_validated_clones.csv`

## Tiered Benchmarking Strategy

| Tier | Samples | Purpose | Data Size | Status |
|------|---------|---------|-----------|--------|
| **1 — Pilot** | 4 clones (1 parent + 3 evolved) | Pipeline smoke test, end-to-end validation | ~4 GB | Complete |
| **2 — CRISPR + CNV** | 85 clones + parent | High-confidence SNV + CNV benchmark | ~40 GB | Planned |
| **3 — Full cohort** | 355 clones + parents | Comprehensive benchmark across all 80 compounds | ~170 GB | Future |

### Tier 2 Details (85 clones: 64 CRISPR-validated + 21 CNV-only)

Tier 2 combines two high-confidence subsets to benchmark both SNV callers and CNV tools:

**CRISPR-validated clones (64 with SRR, from Sup 7 → Sup 4 matching):**
- **48 distinct mutations** across **37 genes** (including YRR1, ERG9, TUP1, VMA16, ACT1, etc.)
- **32 compounds** (MMV1078458, CBR668, MMV665852, KAE609, diethylstilbestrol, etc.)
- Mix of **SNVs** (missense, nonsense) across **all 16 chromosomes + Mito**
- 2 of these clones also have CNV events reported in Sup 5

**CNV-only clones (21, from Sup 5 not in CRISPR set):**
- **21 additional CNV events** (aneuploidies and intrachromosomal amplifications)
- Without these, Tier 2 would have only 2 CNV events — insufficient for tool benchmarking
- All 21 have SRR accessions in the sample dictionary

**Combined**: 23 clones with CNV events (for CNVKit/Control-FREEC), 41 compounds represented.

Benchmarking against Tier 2 lets us measure:
1. **SNV Recall**: Do we detect all 48 CRISPR-validated mutations?
2. **SNV Precision**: How many of our calls match Sup 4 (broader truth set)?
3. **CNV Sensitivity**: Do CNVKit/Control-FREEC detect all 24 CNV events across 23 clones?

## Differences from Current Pipeline (CEN.PK / Pereira Benchmark)
| Feature | Pereira (current) | Ottilie (new) |
|---------|-------------------|---------------|
| Strain | CEN.PK113-7D | ABC16-GM (S288C background) |
| Reference | draft_ref52 (custom) | S288C R64-1-1 (standard) |
| Samples | 17 (7 clonal + 10 spore-seq) | 363 clones |
| Truth set | 24 SNVs (Table S8) | 1,405 variants + 45 CRISPR-validated |
| Selection | Adipic acid tolerance | 80 different xenobiotics |
| Ploidy | Haploid/Diploid | Haploid (GM strain) |

## Implications for Pipeline
- Need S288C reference genome (publicly available, well-annotated)
- SnpEff cache: standard S288C should work (no custom cache needed)
- Larger sample set = more robust benchmarking statistics
- CRISPR-validated subset provides high-confidence truth set
- Standard reference = easier comparison with published tools
- CNV benchmarking feasible: our pipeline runs CNVKit + Control-FREEC vs paper's GATK DiagnoseTargets
