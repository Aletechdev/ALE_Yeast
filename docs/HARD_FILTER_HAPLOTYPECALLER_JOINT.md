# Hard Filter HaplotypeCaller Joint VCF (`--hard_filter_haplotypecaller_joint`)

## Status: FIXED (March 2026) - `--force` added to `bcftools norm`

## What It Does

The `--hard_filter_haplotypecaller_joint` flag enables a post-processing step that:
1. Splits multi-allelic variants into bi-allelic records (`bcftools norm -m -`)
2. Applies hard quality filters on individual VCFs extracted from joint calling

Filter criteria (from `conf/modules/custom_haplotypecaller_joint_filter.config`):
```
FILTER="PASS" & FORMAT/GQ>=20 & FORMAT/DP>=8 & FORMAT/AD[0:1]/(FORMAT/AD[0:0]+FORMAT/AD[0:1])>=0.8
```

## Why It Was Disabled

**`bcftools norm` fails with exit code 255** on individual VCFs extracted from joint calling:

```
Error at chr10:27882, the tag PL has wrong number of fields. Use --force to proceed anyway.
```

### Root Cause

When HaplotypeCaller performs joint calling across multiple samples, the `PL` (Phred-scaled Likelihoods) tag is sized for all genotype combinations across all samples. After splitting the joint VCF into individual sample VCFs (via `--split_haplotypecaller_joint_vcf`), the PL field retains entries that don't match the expected count for a single sample. `bcftools norm` rejects this inconsistency by default.

### Fix Applied

Added `--force` to the `bcftools norm` command in:
```
nf-core-sarek_3.5.1/3_5_1/subworkflows/local/vcf_filter_haplotypecaller_joint/bcftools/hard_filter/main.nf
```

This tells bcftools to proceed despite the PL tag inconsistency, which is safe because the PL field is not used by the downstream hard filter (which operates on GQ, DP, and AD).

## Related Files

- **Process module**: `subworkflows/local/vcf_filter_haplotypecaller_joint/bcftools/hard_filter/main.nf`
- **Subworkflow**: `subworkflows/local/vcf_filter_haplotypecaller_joint/main.nf`
- **Config**: `conf/modules/custom_haplotypecaller_joint_filter.config`
- **Run script**: `bin/CENPK_run_sarek_351_all.sh` (flag removed from line 11)

## Alternative Approach

The joint VCF already has soft filtering via `VARIANTFILTRATION_FALLBACK` (see CLAUDE.md). Individual sample VCFs from `--split_haplotypecaller_joint_vcf` inherit those FILTER annotations. To extract high-confidence variants:

```bash
bcftools view -f PASS sample.haplotypecaller.from_joint_calling.vcf.gz -O z -o sample_PASS.vcf.gz
```

This avoids the PL tag issue entirely since it doesn't require `bcftools norm`.
