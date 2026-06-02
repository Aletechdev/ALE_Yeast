# Soft Filter: HaplotypeCaller Joint VCF (`VARIANTFILTRATION_FALLBACK`)

## Overview

GATK VariantFiltration is applied as a **soft filter** (also called "filter annotation") on the joint HaplotypeCaller VCF. It **populates the FILTER column** with `PASS` or named filter tags but **does not remove any variants**.

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

Filters are split by variant type per GATK best practices ([section C: SNPs, section D: INDELs](https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering)). INDELs receive fewer and more lenient filters because they naturally show more strand bias and positional bias due to alignment difficulties.

### Universal Filters (apply to both SNPs and INDELs)

| Filter Name | Expression | What It Measures |
|-------------|-----------|------------------|
| **QD_filter** | `QD < 2.0` | **Quality by Depth** — QUAL normalized by total read depth. Low QD means variant quality is not supported by sufficient evidence per read. |
| **QUAL_filter** | `QUAL < 30.0` | **Site Quality** — Phred-scaled probability of non-reference allele. QUAL < 30 means >0.1% chance the site is homozygous reference. |

### SNP-Only Filters (GATK section [C])

These use `vc.isSNP()` to restrict to SNP records only.

| Filter Name | Expression | What It Measures |
|-------------|-----------|------------------|
| **FS_filter** | `vc.isSNP() && FS > 60.0` | **Fisher Strand bias** — Phred-scaled p-value for strand bias. High FS suggests PCR or sequencing artifact. |
| **SOR_filter** | `vc.isSNP() && SOR > 3.0` | **Strand Odds Ratio** — Symmetric odds ratio test for strand bias. Preferred over FS at high depth. |
| **MQ_filter** | `vc.isSNP() && MQ < 40.0` | **Mapping Quality** — RMS mapping quality. Low MQ means reads map to multiple locations (repetitive region). |
| **MQRankSum_filter** | `vc.isSNP() && MQRankSum < -12.5` | **MQ Rank Sum Test** — Compares mapping quality of REF vs ALT reads. Large negative = ALT reads map poorly → mismapping artifact. |
| **ReadPosRankSum_filter** | `vc.isSNP() && ReadPosRankSum < -8.0` | **Read Position Rank Sum Test** — Compares read positions of REF vs ALT. Negative = ALT at read ends → sequencing error. |

### INDEL-Only Filters (GATK section [D])

These use `vc.isIndel()` to restrict to INDEL records only. Per GATK, INDELs do **not** receive SOR, MQ, or MQRankSum filters.

| Filter Name | Expression | Why More Lenient |
|-------------|-----------|------------------|
| **FS_INDEL_filter** | `vc.isIndel() && FS > 200.0` | INDELs cause alignment artifacts that inflate FS. Threshold is 3.3x higher than SNP (200 vs 60). |
| **ReadPosRankSum_INDEL_filter** | `vc.isIndel() && ReadPosRankSum < -20.0` | INDELs near read ends cause soft-clipping. Threshold is 2.5x more lenient than SNP (-20 vs -8). |

### Filter Application Logic

Each filter is evaluated independently. A variant can accumulate **multiple filter tags** (semicolon-delimited):

```
FILTER=PASS                          # Passes all filters
FILTER=QD_filter                     # Fails one filter
FILTER=QD_filter;FS_filter;SOR_filter  # Fails multiple filters
```

SNP-only filters (`vc.isSNP()`) are skipped for INDELs and vice versa. A SNP will never receive `FS_INDEL_filter`, and an INDEL will never receive `SOR_filter`.

### Important: `TYPE==` JEXL Syntax Bug

The `TYPE==SNP` and `TYPE==INDEL` JEXL expressions **silently match nothing** in GATK VariantFiltration — they are syntactically accepted but produce zero filter hits. This was discovered during Ottilie Tier 2 validation (June 2026).

| Syntax | Result |
|--------|--------|
| `TYPE==SNP && SOR > 3.0` | 0 matches (broken) |
| `vc.isSNP() && SOR > 3.0` | 135 matches (correct) |
| `TYPE==INDEL && SOR > 3.0` | 0 matches (broken) |
| `vc.isIndel() && SOR > 3.0` | 94 matches (correct) |

**Always use `vc.isSNP()` / `vc.isIndel()`** for type-specific filtering in GATK VariantFiltration.

## Filter Performance

### Pre-fix baseline (CEN.PK 6 samples, TYPE== era — INDEL filters were no-ops)

From 1,748 total variants:

| Outcome | Count | Percentage |
|---------|-------|------------|
| **PASS** | 737 | 42.2% |
| Flagged (1+ filters) | 1,011 | 57.8% |

### Ottilie Tier 2 (86 samples, vc.isSNP()/vc.isIndel() fix)

From 1,521 total variants (823 SNPs, 698 INDELs):

| Metric | Before fix | After fix |
|--------|-----------|-----------|
| INDEL PASS rate | 514/698 (73.6%) | ~677/698 (97.0%) |
| INDELs wrongly filtered by SNP thresholds | 163 | 0 |
| Truth set sensitivity (PASS only) | 332/343 (96.8%) | 333/343 (97.1%) |

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
1. VQSR recalibrated VCF (when known sites available — e.g., human)
2. Filter-annotated VCF (fallback for custom genomes — our case)
3. Unfiltered VCF (should not happen)

## Configuration

**Config file**: `conf/modules/joint_germline.config`

**Workflow file**: `subworkflows/local/bam_joint_calling_germline_gatk/main.nf`

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

- **QD_filter (QD < 2.0)**: Most restrictive filter. Yeast has a smaller genome with higher per-base coverage; consider whether QD < 1.5 or QD < 1.0 would be more appropriate.
- **MQ_filter (MQ < 40.0)**: Yeast genome has fewer repetitive regions than human, so most reads should map uniquely (MQ=60). This filter likely catches genuine mapping issues.
- **SOR/FS thresholds**: Deep ALE sequencing may amplify natural strand bias. Ottilie Tier 2 validation showed 5 of 8 missed truth mutations were lost to SOR_filter. Monitor whether real mutations are being incorrectly flagged.

These thresholds should be validated against known ALE mutation types before relaxation.

## Verification Script

After changing filter expressions, run `docs/variant-calling/haplotypecaller/verify_soft_filter_fix.sh` to spot-check that INDELs are recovered and SNPs remain correctly filtered.
