# Ottilie Tier 2 — SNV/INDEL Concordance Validation Report

**Date**: 2026-05-19
**Pipeline**: nf-core/sarek 3.5.1 (forked), HaplotypeCaller joint germline
**Truth set**: Ottilie et al. (2022) Commun Biol 5:128, Supplementary Data 4
**Samples**: 85 evolved + 1 parent (NODRUG-GM2)

## Results

| Metric | Value |
|--------|-------|
| Overall sensitivity | **339/343 (98.8%)** |
| SNP sensitivity | 323/326 (99.1%) |
| INDEL sensitivity | 16/17 (94.1%) |
| Samples evaluated | 85 (of which 63 had truth set mutations) |

## Missed Variants (4/343)

| Sample | Position | Gene | Type | Root cause |
|--------|----------|------|------|------------|
| DDD01027481--8_R3a | I:59020 G>A | PTA1 | SNP | No alt reads (73x ref, MAPQ=60) — truth set discrepancy |
| MMV1078458--5R3a | VIII:485367 T>A | ERG9 | SNP | No alt reads (48x ref, MAPQ=60) — truth set discrepancy |
| MMV085203-11R3a | III:316617 T>G | intergenic | SNP | Low coverage (~7 reads) — subtelomeric region |
| GNFpf2740--15_R5a | XII:1071524 (45bp del) | intergenic | INDEL | rDNA tandem repeat (~200 copies), del diluted to ~0.5% AF |

**None of the 4 misses are pipeline failures.** The pipeline correctly identifies variants where evidence exists in the sequencing data.

## Notable Findings

### Multi-allelic sites (resolved during validation)
7 variants initially appeared missed due to multi-allelic VCF representation:
- **YRR1** XV:640160 — truth `C>G`, pipeline `C>G,A` (4 samples)
- **YRM1** XV:655947 — truth `G>A`/`G>T`, pipeline `G>A,T` (3 samples)

Both are zinc cluster transcription factors recurrently mutated across drug treatments — consistent with known ALE adaptation targets. The concordance script was updated to handle multi-allelic matching on both sides.

### Multi-nucleotide variants (MNVs)
2 truth set entries have multi-position coordinates:
- MMV665852--13R3b: XV:640157,640159 C>A (YRR1) — matched on first position
- MMV665882--17_R4b: VIII:184523,184524 C,A>T,G (RRF1) — not in Tier 2 batch

### PAU6 soft-filtering (pilot run observation)
XIV:781921 G>A (PAU6 missense) in pilot sample Doxorubicin16-R2b was detected but soft-filtered (`MQ_filter;SOR_filter`, QUAL=1037.9). PAU6 is one of 24 seripauperin paralogs — 66% of reads at this position have MAPQ=0. Soft-filtering is appropriate.

## Reproducibility

### Scripts
| File | Purpose |
|------|---------|
| `snv_indel_concordance.py` | Main concordance analysis (dynamic sample mapping) |
| `investigate_missed_snv_indel.sh` | Pileup investigation for each missed variant |

### Generated files
| File | Contents |
|------|----------|
| `tier2_results/snv_indel_concordance_tier2.csv` | Per-sample sensitivity/precision table |
| `tier2_results/snv_indel_concordance_tier2.log` | Full console output |
| `tier2_results/missed_variants_investigation.txt` | Pileup evidence for all 4 missed variants |
| `tier2_results/VALIDATION_REPORT.md` | This report |

### How to reproduce
```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
cd /home/azureuser/Docs/ALE_nextflow

# 1. Run concordance
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/snv_indel_concordance.py \
    --output-dir output_ottilie_tier2 \
    --csv docs/benchmarking/ottilie_xenobiotic_ale/04_validate/tier2_results/snv_indel_concordance_tier2.csv

# 2. Investigate missed variants
bash docs/benchmarking/ottilie_xenobiotic_ale/04_validate/investigate_missed_snv_indel.sh output_ottilie_tier2
```

## Dependencies
- `sample_name_dictionary.csv` — maps Sup Data 4 clone names to pipeline sample names
- `sup_4_42003_2022_3076_MOESM6_ESM.xlsx` — Ottilie et al. truth set
- `bcftools`, `samtools`, `openpyxl` (Python)
