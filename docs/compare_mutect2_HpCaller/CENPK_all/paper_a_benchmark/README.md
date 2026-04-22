# VCF Filtering Guidelines Based on Benchmark Mutation Analysis

## Overview

This document provides evidence-based filtering guidelines for Mutect2 and HaplotypeCaller VCF files, derived from analysis of 24 confirmed benchmark mutations across 5 ALE (Adaptive Laboratory Evolution) samples.

## Background & Theory

### Variant Calling in ALE Experiments

**Adaptive Laboratory Evolution (ALE)** experiments generate populations with evolved mutations that differ from traditional human genomics:

- **Fixed mutations**: Many variants reach near-fixation (AF ~0.7-0.9) in evolved populations
- **Population-level changes**: Focus on mutations that provide adaptive advantage
- **Custom reference**: Yeast genomes lack comprehensive variant databases (no dbSNP equivalent)
- **Tumor-normal paradigm**: ALE uses evolved vs ancestral comparisons, not tumor vs normal tissue

### Multi-Tool Approach

**Mutect2 vs HaplotypeCaller**:
- **Mutect2**: Designed for somatic mutations, more sensitive to low-frequency variants
- **HaplotypeCaller**: Designed for germline variants, more conservative calling
- **Consensus variants**: 321 variants detected by both tools, including all 24 benchmark mutations

## Benchmark Analysis Results

### Dataset Summary
- **Total benchmark mutations**: 24 confirmed variants across 5 samples
- **Consensus coverage**: 100% (24/24 benchmark mutations found in consensus)
- **Sample distribution**:
  - ALE_Exp1_A1-F6-I1-R1: 4 mutations
  - ALE_Exp1_A3-F3-I1-R1: 3 mutations
  - ALE_Exp1_A4-F5-I1-R1: 5 mutations
  - ALE_Exp1_A5-F4-I1-R1: 6 mutations
  - ALE_Exp1_A6-F6-I1-R1: 6 mutations

### Quality Score Analysis

#### Mutect2 Statistics (from benchmark mutations)
| Metric | Min | Max | Mean | Recommended Threshold |
|--------|-----|-----|------|---------------------|
| TLOD   | 54.44 | 203.29 | 132.4 | ≥ 50 |
| DP     | 382 | 695 | 513 | ≥ 20 |
| NLOD   | 15.6 | 32.67 | 20.6 | ≥ 10 |
| MBQ    | 36,36 | 36,36 | 36,36 | ≥ 30 |
| MMQ    | 60,60 | 60,60 | 60,60 | ≥ 50 |

#### HaplotypeCaller Statistics (from benchmark mutations)
| Metric | Min | Max | Mean | Recommended Threshold |
|--------|-----|-----|------|---------------------|
| QUAL   | 804.44 | 2841.22 | 1873.5 | ≥ 100 |
| QD     | 25.14 | 31.55 | 28.2 | ≥ 20 |
| FS     | 0.0 | 4.07 | 1.4 | ≤ 10 |
| MQ     | 56.61 | 60.0 | 59.3 | ≥ 50 |
| SOR    | 0.237 | 1.051 | 0.6 | ≤ 3 |
| DP     | 313 | 516 | 381 | ≥ 20 |

### Allele Frequency Patterns
- **Benchmark mutations**: AF = 0.75 - 0.853 (high frequency, near-fixed)
- **Genotype calls**: All called as 0/1 (heterozygous) by HaplotypeCaller
- **Population context**: Represents evolved populations with mixed ancestral/evolved cells

## Filtering Recommendations

### 🔥 High-Confidence Filters (Strict - for final publication dataset)

**Mutect2**:
```bash
bcftools filter -i 'INFO/TLOD>=100 && INFO/DP>=50 && INFO/NLOD>=15 && INFO/MBQ[0]>=30 && INFO/MBQ[1]>=30'
```

**HaplotypeCaller**:
```bash
bcftools filter -i 'QUAL>=500 && INFO/QD>=25 && INFO/FS<=5 && INFO/MQ>=55 && INFO/SOR<=2'
```

**Expected result**: High precision, captures well-supported variants

### 🧪 Balanced Filters (Recommended for most ALE analyses)

**Mutect2**:
```bash
bcftools filter -i 'INFO/TLOD>=50 && INFO/DP>=20 && INFO/NLOD>=10 && INFO/MBQ[0]>=30 && INFO/MBQ[1]>=30'
```

**HaplotypeCaller**:
```bash
bcftools filter -i 'QUAL>=100 && INFO/QD>=20 && INFO/FS<=10 && INFO/MQ>=50 && INFO/SOR<=3'
```

**Expected result**: Good balance of sensitivity and specificity for ALE experiments

### 🔍 Permissive Filters (Sensitive - for discovery and validation)

**Mutect2**:
```bash
bcftools filter -i 'INFO/TLOD>=30 && INFO/DP>=15 && INFO/NLOD>=5'
```

**HaplotypeCaller**:
```bash
bcftools filter -i 'QUAL>=50 && INFO/QD>=15 && INFO/FS<=15 && INFO/MQ>=40'
```

**Expected result**: Higher sensitivity, may include some technical artifacts

## Implementation Guidelines

### Filter Selection Strategy

1. **Start with Balanced Filters**: Recommended for initial analysis
2. **Validate with benchmarks**: Ensure all 24 benchmark mutations pass filters
3. **Adjust based on results**:
   - Too many variants → use High-Confidence filters
   - Missing expected variants → use Permissive filters

### Quality Assessment Workflow

```bash
# 1. Apply filters
bcftools filter -i 'FILTER_EXPRESSION' input.vcf.gz > filtered.vcf

# 2. Check benchmark coverage
bcftools view -r chr12:171072,chr13:2746,chr15:783260 filtered.vcf

# 3. Count variants
bcftools stats filtered.vcf | grep "number of records"

# 4. Validate against known mutations
# Compare with benchmark mutation lists in CSV files
```

### Multi-Tool Integration

**Consensus Approach** (Recommended):
```bash
# 1. Filter each tool separately
bcftools filter -i 'MUTECT2_FILTERS' mutect2.vcf.gz > mutect2_filtered.vcf
bcftools filter -i 'HAPLOTYPECALLER_FILTERS' haplotypecaller.vcf.gz > hc_filtered.vcf

# 2. Find intersection (high confidence)
bcftools isec -n+2 mutect2_filtered.vcf hc_filtered.vcf

# 3. Union for comprehensive analysis
bcftools merge mutect2_filtered.vcf hc_filtered.vcf
```

## Key Insights from Benchmark Analysis

### ✅ Validation Results
- **100% benchmark coverage**: All 24 confirmed mutations detected by both tools
- **High-quality indicators**: TLOD ≥ 50, QUAL ≥ 800 for benchmark mutations
- **Consistent mapping quality**: MQ = 60 across all benchmark sites
- **Low strand bias**: FS ≤ 4.07, indicating reliable variant calls

### 🎯 ALE-Specific Considerations
- **Fixed mutations predominate**: High AF (0.75-0.85) typical of evolved populations
- **Population genetics**: Focus on variants that reached significant frequency
- **Tool complementarity**: Mutect2 and HaplotypeCaller capture overlapping but distinct variant sets

### ⚠️ Filtering Trade-offs
- **Precision vs Sensitivity**: Stricter filters reduce false positives but may miss early evolution events
- **Sample diversity**: Different samples may require different stringency based on evolution stage
- **Downstream analysis**: Consider experimental goals when selecting filter stringency

## Files in This Directory

- `ALE_Exp1_A1-F6-I1-R1_benchmark.csv`: Benchmark mutations for sample A1-F6-I1-R1
- `ALE_Exp1_A3-F3-I1-R1_benchmark.csv`: Benchmark mutations for sample A3-F3-I1-R1
- `ALE_Exp1_A4-F5-I1-R1_benchmark.csv`: Benchmark mutations for sample A4-F5-I1-R1
- `ALE_Exp1_A5-F4-I1-R1_benchmark.csv`: Benchmark mutations for sample A5-F4-I1-R1
- `ALE_Exp1_A6-F6-I1-R1_benchmark.csv`: Benchmark mutations for sample A6-F6-I1-R1
- `consensus_variants.txt`: 321 consensus variants detected by both tools
- `README.md`: This documentation file

## Future Directions

### Potential Improvements
1. **Temporal analysis**: Develop filters for early vs late evolution timepoints
2. **Population frequency**: Incorporate allele frequency thresholds based on evolution stage
3. **Functional annotation**: Weight filtering based on predicted functional impact
4. **Machine learning**: Train models on benchmark data for optimal filter combinations

### Validation Recommendations
1. **Sanger sequencing**: Validate subset of filtered variants
2. **Functional testing**: Confirm adaptive advantage of filtered mutations
3. **Cross-experiment validation**: Test filters on independent ALE experiments
4. **Tool updates**: Re-evaluate thresholds with newer tool versions

## Contact & References

This analysis was conducted as part of the NF_ALE pipeline development for yeast adaptive laboratory evolution experiments. The filtering guidelines are specifically optimized for:
- Yeast (Saccharomyces cerevisiae) genomes
- Population-based evolution experiments
- Multi-tool variant calling approaches
- Custom reference genomes without comprehensive variant databases

For questions or suggestions regarding these filtering guidelines, please refer to the main pipeline documentation.