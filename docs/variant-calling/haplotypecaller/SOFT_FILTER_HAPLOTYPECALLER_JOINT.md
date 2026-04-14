# Soft Filter: HaplotypeCaller Joint VCF (`VARIANTFILTRATION_FALLBACK`)

## Overview

GATK VariantFiltration is applied as a **soft filter** (also called "filter annotation") on the joint HaplotypeCaller VCF. It **populates the FILTER column** with `PASS` or named filter tags but **does not remove any variants**. All 1,748 variants remain in the output; 737 (42.2%) are marked `PASS`.

This was implemented as a fallback because VQSR (Variant Quality Score Recalibration) requires known variant resources (e.g., dbSNP, HapMap) that don't exist for our custom yeast genome.

## Output File

```
output_all/variant_calling/haplotypecaller/joint_variant_calling/
    HaplotypeCaller_joint_calling_soft_filtered.vcf.gz
    HaplotypeCaller_joint_calling_soft_filtered.vcf.gz.tbi
```

## Key Concept: Cohort-Level Metrics

All filters operate on **INFO-level (cohort-wide) annotations**, not per-sample FORMAT fields. In a joint VCF with N samples:

- **INFO/DP** = total read depth summed across all samples at that site
- **QUAL** = Phred-scaled site-level quality score across all samples
- **QD** = QUAL divided by INFO/DP (quality normalized by total depth)
- **FS, SOR** = strand bias computed from all reads across all samples
- **MQ** = root mean square mapping quality across all reads at the site
- **MQRankSum, ReadPosRankSum** = rank sum tests comparing REF vs ALT reads across all samples

This means a variant can be marked `PASS` at the cohort level but still have poor quality in a specific sample. That's why the downstream [hard filter](HARD_FILTER_HAPLOTYPECALLER_JOINT.md) checks **per-sample** FORMAT fields (GQ, FORMAT/DP, FORMAT/AD).

## Filter Definitions

### SNP Filters

| Filter Name | Expression | What It Measures | Why It Matters |
|-------------|-----------|------------------|----------------|
| **QD_filter** | `QD < 2.0` | **Quality by Depth** - QUAL score normalized by total read depth (INFO/DP). Low QD means the variant quality is not supported by sufficient evidence per read. | Catches low-confidence calls inflated by high depth. Most restrictive filter in our data (49.1% of flagged variants). |
| **FS_filter** | `FS > 60.0` | **Fisher Strand bias** - Phred-scaled p-value from Fisher's exact test for strand bias. Tests whether ALT allele is seen disproportionately on one strand vs the other. | High FS indicates the variant may be a sequencing or PCR artifact. Real variants should appear on both strands roughly equally. Scale: 0 = no bias, higher = more bias. |
| **SOR_filter** | `SOR > 3.0` | **Strand Odds Ratio** - Similar to FS but uses a symmetric odds ratio test that is better for high-depth data. Less sensitive to large sample sizes than Fisher's test. | Complementary strand bias metric. Preferred over FS when depth is very high (common in ALE experiments with deep sequencing). |
| **MQ_filter** | `MQ < 40.0` | **Mapping Quality** - Root mean square of mapping qualities of all reads at the site. MQ=60 is the maximum (unique mapping); lower values mean reads map to multiple locations. | Low MQ suggests the region is repetitive or has paralogs. Variants in poorly-mapped regions are unreliable. MQ < 40 is a strong signal of ambiguous mapping. |
| **MQRankSum_filter** | `MQRankSum < -12.5` | **Mapping Quality Rank Sum Test** - Compares mapping qualities of reads supporting REF vs ALT alleles using a Mann-Whitney U test. Negative = ALT reads have worse mapping quality. | Large negative values mean ALT-supporting reads map poorly compared to REF reads, suggesting the "variant" is actually a mismapping artifact. |
| **ReadPosRankSum_filter** | `ReadPosRankSum < -8.0` | **Read Position Rank Sum Test** - Compares positions within reads where REF vs ALT alleles are observed. Negative = ALT alleles tend to appear at read ends. | Variants seen only at read ends are often sequencing errors (quality drops at read termini). Real variants should appear uniformly across read positions. |
| **QUAL_filter** | `QUAL < 30.0` | **Site Quality** - Phred-scaled probability that the site has a non-reference allele in at least one sample. QUAL=30 means 99.9% confidence. | Basic quality threshold. QUAL < 30 means >0.1% chance the site is actually homozygous reference across all samples. |

### INDEL-Specific Filters (More Lenient)

INDELs naturally show more strand bias and positional bias than SNPs due to alignment difficulties, so thresholds are relaxed.

| Filter Name | Expression | Why More Lenient |
|-------------|-----------|------------------|
| **FS_INDEL_filter** | `TYPE==INDEL && FS > 200.0` | INDELs cause alignment artifacts that inflate FS. Threshold is 3.3x higher than SNP filter (200 vs 60). |
| **SOR_INDEL_filter** | `TYPE==INDEL && SOR > 10.0` | Same rationale as FS. Threshold is 3.3x higher than SNP filter (10 vs 3). |
| **ReadPosRankSum_INDEL_filter** | `TYPE==INDEL && ReadPosRankSum < -20.0` | INDELs near read ends cause soft-clipping that shifts apparent positions. Threshold is 2.5x more lenient than SNP filter (-20 vs -8). |

### Filter Application Logic

A variant can accumulate **multiple filter tags**. The FILTER column is semicolon-delimited:

```
# Single filter failure:
FILTER=QD_filter

# Multiple filter failures:
FILTER=QD_filter;FS_filter;SOR_filter

# Passes all filters:
FILTER=PASS
```

**Important**: INDEL-specific filters are combined with `TYPE==INDEL &&`, so they only apply to INDELs. SNP filters apply to all variant types (SNPs and INDELs both). This means an INDEL can be flagged by both SNP and INDEL filters.

## Filter Performance (Test Data)

From 1,748 total variants in the joint VCF:

| Outcome | Count | Percentage |
|---------|-------|------------|
| **PASS** | 737 | 42.2% |
| Flagged (1+ filters) | 1,011 | 57.8% |

Most common filter flags:

| Filter | Variants Flagged | % of Total |
|--------|-----------------|------------|
| QD_filter | 831 | 49.1% |
| SOR_filter | 278 | 16.4% |
| MQ_filter | 107 | 6.3% |
| FS_filter | 77 | 4.5% |

## Pipeline Position

```
GenomicsDBImport → GenotypeGVCFs → MergeVCFs (joint_germline.vcf.gz)
                                        │
                                        ├── VQSR (fails for custom genomes)
                                        │
                                        └── VARIANTFILTRATION_FALLBACK ──► soft_filtered.vcf.gz
                                                                                │
                                                     ┌──────────────────────────┘
                                                     │
                                              Split Joint VCF (--split_haplotypecaller_joint_vcf)
                                                     │
                                              Hard Filter (--hard_filter_haplotypecaller_joint)
                                              [per-sample FORMAT fields: GQ, DP, AD]
```

**Three-tier priority logic** (in workflow):
1. VQSR recalibrated VCF (when known sites available - e.g., human)
2. Filter-annotated VCF (fallback for custom genomes - our case)
3. Unfiltered VCF (should not happen)

## Configuration

**Config file**: `conf/modules/joint_germline.config` (lines 87-108)

**Workflow file**: `subworkflows/local/bam_joint_calling_germline_gatk/main.nf` (lines 70-75, 141-161)

## Relationship to Hard Filter

| Aspect | Soft Filter (this doc) | [Hard Filter](HARD_FILTER_HAPLOTYPECALLER_JOINT.md) |
|--------|----------------------|-----------------------------------------------------|
| Tool | GATK VariantFiltration | bcftools filter |
| Scope | Cohort-level (INFO fields) | Per-sample (FORMAT fields) |
| Action | Tags FILTER column | Removes variants entirely |
| Input | Joint VCF (all samples) | Individual VCFs (split from joint) |
| Metrics | QD, FS, SOR, MQ, QUAL, RankSum tests | GQ, FORMAT/DP, FORMAT/AD |
| Prerequisite | None | Requires `FILTER=PASS` from soft filter |

## Extracting PASS Variants

```bash
# From joint VCF (all samples, cohort-level PASS):
bcftools view -f PASS HaplotypeCaller_joint_calling_soft_filtered.vcf.gz -O z -o joint_PASS.vcf.gz

# Count PASS vs flagged:
bcftools view -H -f PASS file.vcf.gz | wc -l    # PASS count
bcftools view -H file.vcf.gz | wc -l             # Total count
```

## Considerations for Yeast ALE

The current filter thresholds are based on **GATK best practices for human data**. Potential adjustments for yeast:

- **QD_filter (QD < 2.0)**: Most restrictive filter (49.1%). Yeast has a smaller genome with higher per-base coverage; consider whether QD < 1.5 or QD < 1.0 would be more appropriate.
- **MQ_filter (MQ < 40.0)**: Yeast genome has fewer repetitive regions than human, so most reads should map uniquely (MQ=60). This filter likely catches genuine mapping issues.
- **SOR/FS thresholds**: Deep ALE sequencing may amplify natural strand bias. Monitor whether real mutations are being incorrectly flagged.

These thresholds should be validated against known ALE mutation types before relaxation.
