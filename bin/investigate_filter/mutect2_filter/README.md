# Mutect2 Filtering Strategy Investigation

**Date**: 2025-01-04  
**Purpose**: Investigate filtering strategies for yeast ALE Mutect2 variants to inform bench scientist discussion  

## Overview

This investigation analyzes raw Mutect2 output to understand different filtering approaches for yeast Adaptive Laboratory Evolution (ALE) experiments. Unlike cancer research, ALE studies have different biological questions that may require different variant filtering strategies.

## Key Research Questions

1. **Should variants present in original strain be reported?**
   - Cancer approach: Remove all variants in normal (acquired-mutations-only [somatic])
   - ALE approach: May want pre-existing variation, frequency changes

2. **What confidence threshold is appropriate?**
   - High stringency: Only clear adaptive mutations
   - Medium stringency: Balance sensitivity vs precision
   - Low stringency: Complete mutational landscape

3. **AF-based vs GT-based filtering?**
   - AF-based: Use allele frequency thresholds
   - GT-based: Focus on genotype changes (0/0 → 0/1)

## Data Source

**Raw Mutect2 VCF**: `output_NCYC495/variant_calling/mutect2/A10-F47-I1-R1_vs_A0-F0-I1-R1/A10-F47-I1-R1_vs_A0-F0-I1-R1.mutect2.vcf.gz`

**Sample Information**:
- **Normal (Ancestral)**: NCYC495_A0-F0-I1-R1 (starting strain)
- **Evolved**: NCYC495_A10-F47-I1-R1 (evolved strain after F47 generations)

## Key Findings Summary

- **Total raw variants**: 45,139
- **No AF=0 variants**: Mutect2 minimum AF ~4%
- **AF distribution in normal**: 27.7% have AF<5% (potential acquired mutations)
- **GT-based candidates**: Found 0/0→0/1 transitions with dramatic AF increases
- **Current filtering reduces**: 45,139 → ~4,200 variants
- **NLOD impact**: Only affects 7-9 variants (minimal)

## Filtering Strategy Examples

### Example 1: Low Confidence Variants (TLOD < 6)
```
Position: AECK01000001:2758 G>A
TLOD=5.15 NLOD=2.71 Total_DP=37
Normal: AF=8.8% DP=9  |  Evolved: AF=7.3% DP=28
```
- **Conservative filter**: REMOVE (low confidence)
- **Permissive filter**: KEEP (might be real low-frequency change)
- **Question**: Is this noise or a real frequency decrease during evolution?

### Example 2: High Confidence but Present in Normal (NLOD < 0)
```
Position: AECK01000001:774017 T>C  
TLOD=35.55 NLOD=-52.37 Total_DP=35
Normal: AF=76.2% DP=21  |  Evolved: AF=66.6% DP=14
```
- **Cancer-focused**: REMOVE (present in normal = germline)
- **ALE-focused**: KEEP? (frequency change during evolution)
- **Question**: Should frequency shifts in pre-existing variants be tracked?

### Example 3: Medium Quality Borderline Variants
```
Position: AECK01000001:378 G>A
TLOD=8.13 NLOD=2.71 Total_DP=50  
Normal: AF=9.1% DP=11  |  Evolved: AF=10.8% DP=39
```
- **Moderate filter**: BORDERLINE (depends on AF difference threshold)
- **Question**: Is 1.7% AF increase biologically meaningful?
- **Current filter**: REMOVE (below 8% difference threshold)

### Example 4: Borderline TLOD Threshold Variants
```
Position: AECK01000001:1536 AG>TA
Normal: AF=10.0% DP=8 → Evolved: AF=17.2% DP=29
TLOD=12.3 NLOD=2.41
```
- **Current TLOD filter (≥12)**: KEEP (12.3 just passes threshold)
- **AF-based filter**: KEEP (evolved AF=17.2% > 5%, AF difference=7.2% < 8%)
- **Question**: Should variants just above/below TLOD=12 be treated differently?
- **Note**: Small changes in threshold (11.5 vs 12.5) significantly impact variant retention

### Example 5: Large AF Increase (Potential Adaptive Mutation [True Somatic])
```
Position: AECK01000001:27887 A>G  
Normal: AF=4.6% → Evolved: AF=22.4% (Δ=17.8%)
TLOD=14.22 NLOD=5.93
```
- **Question**: Is 4.6% background noise or real low-level variant?
- **ALE relevance**: Dramatic frequency increase suggests strong selection
- **Current filter**: KEEP (meets all current thresholds)

## Key Numbers Summary
- **Total raw variants**: 45,139
- **Normal AF=0**: 0 variants (0%)  
- **Normal AF<5%**: 12,502 variants (27.7%) - Potential acquired mutations
- **NLOD<0**: 7 variants (likely germline/artifacts)
- **NLOD<2**: 9 variants (low confidence acquired mutations)
- **Current filtered output**: ~4,200 variants (90.7% reduction)

## Analysis Commands Used

### Basic Statistics
```bash
# Activate conda environment
source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env

VCF_PATH="/home/azureuser/Docs/ALE_nextflow/output_NCYC495/variant_calling/mutect2/A10-F47-I1-R1_vs_A0-F0-I1-R1/A10-F47-I1-R1_vs_A0-F0-I1-R1.mutect2.vcf.gz"

# Total variants
bcftools view -H "$VCF_PATH" | wc -l

# AF distribution in normal sample
bcftools query -f '[%AF\t]\n' "$VCF_PATH" | awk 'BEGIN { very_low = 0; total = 0 } { if ($1 < 0.05) very_low++; total++ } END { print "AF<5%:", very_low, "(" (very_low*100/total) "%)" }'

# NLOD impact analysis
bcftools query -f '%INFO/NLOD\n' "$VCF_PATH" | awk '$1 < 0 { negative++ } $1 < 2 { low_nlod++ } END { print "NLOD<0:", negative+0; print "NLOD<2:", low_nlod+0 }'
```

## Next Steps

1. Review investigation results with bench scientists
2. Decide on filtering philosophy based on research goals:
   - **Conservative**: Focus on high-confidence newly-acquired mutations
   - **Comprehensive**: Include frequency changes in pre-existing variants
   - **Hybrid**: Combine GT-based + AF-based approaches
3. Implement chosen filtering strategy
4. Validate with known positive/negative controls