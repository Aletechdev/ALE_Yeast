# Ottilie et al. Benchmark Study Context

## Reference
Ottilie et al., "Adaptive laboratory evolution in S. cerevisiae highlights role of transcription factors in fungal xenobiotic resistance", Communications Biology 5:128 (2022)
- PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC8837787/
- DOI: https://www.nature.com/articles/s42003-022-03076-7

## Study Design
- **Organism**: *Saccharomyces cerevisiae* ABC16-Green Monster (GM) strain
  - Modified strain with 16 ABC transporters replaced with GFP
  - NOT CEN.PK (different from current pipeline reference)
- **Reference genome**: S288C assembly R64-1-1 (SNV calling), R64-2-1 (intergenic mapping)
- **Compounds**: ~1,600 screened, 80 yielded resistant clones
- **Selection**: Xenobiotic/drug resistance ALE

## Sequencing Data
- **Samples**: 363 evolved clones sequenced
- **Platform**: Illumina HiSeq 2500 RapidRun mode
- **Read type**: Paired-end, minimum 100 bp
- **Coverage**: Average 54.6x
- **Mapping rate**: 99.7% to reference
- **BioProject**: PRJNA590203
- **Additional SRA**: SRX1745463-SRX1869282 (23 previously published selections)

## Variant Calling (Paper's Methods)
- **Aligner**: BWA-mem with Picard Tools preprocessing
- **Variant caller**: GATK HaplotypeCaller
- **Annotation**: SnpEff
- **Total mutations**: 1,405 (1,286 SNVs + 119 INDELs)

## Truth Set / Validation Data
- **Supplementary Data 4**: Comprehensive mutation list (1,405 variants: 1,286 SNVs + 119 INDELs)
- **Supplementary Data 5**: Copy number variants (24 CNVs: 11 aneuploidies across 10 clones + 13 intrachromosomal amplifications); filtered for ≥2-3x fold coverage change vs parent and spanning ≥4 genes
- **Supplementary Data 7** *(nice-to-have)*: CRISPR/Cas9 validation results (61 alleles tested, 45 confirmed causal) — biological relevance, not prioritized for technical benchmarking
- Key finding: ~25% of compounds had resistance mediated by gain-of-function SNVs in YRR1/YRM1 transcription factors (170 aa domain, 100 independent SNVs)

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
