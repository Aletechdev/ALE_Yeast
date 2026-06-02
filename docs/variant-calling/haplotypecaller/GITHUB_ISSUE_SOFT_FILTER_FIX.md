# Fix: TYPE==SNP/TYPE==INDEL JEXL silently fails in GATK VariantFiltration + split SNP/INDEL filters per GATK best practices

## Bug Summary

`TYPE==SNP` and `TYPE==INDEL` JEXL expressions in GATK VariantFiltration are **silently accepted but match nothing**. This caused 3 INDEL-specific soft filters (`FS_INDEL_filter`, `SOR_INDEL_filter`, `ReadPosRankSum_INDEL_filter`) to be complete no-ops since their introduction. Meanwhile, SNP-strict thresholds (SOR > 3.0, MQ < 40, FS > 60) were incorrectly applied to all variants including INDELs.

## Evidence

Tested on Ottilie Tier 2 joint VCF (1,521 variants: 823 SNPs, 698 INDELs) using GATK 4.x via Docker:

| JEXL Expression | Variants Filtered | Status |
|----------------|-------------------|--------|
| `--filter "TYPE==SNP && SOR > 3.0"` | **0** | Broken (silent no-op) |
| `--filter "TYPE==INDEL && SOR > 3.0"` | **0** | Broken (silent no-op) |
| `--filter "vc.isSNP() && SOR > 3.0"` | **135** | Correct |
| `--filter "vc.isIndel() && SOR > 3.0"` | **94** | Correct |

Both `TYPE==` expressions complete without error but produce all-PASS output. The `vc.isSNP()` / `vc.isIndel()` VariantContext methods work correctly.

## Impact

### INDEL-specific filters were no-ops

These filters in `conf/modules/joint_germline.config` never matched any variants:

```groovy
'--filter-name "FS_INDEL_filter" --filter "TYPE==INDEL && FS > 200.0"',          // 0 matches
'--filter-name "SOR_INDEL_filter" --filter "TYPE==INDEL && SOR > 10.0"',         // 0 matches
'--filter-name "ReadPosRankSum_INDEL_filter" --filter "TYPE==INDEL && ReadPosRankSum < -20.0"'  // 0 matches
```

### INDELs wrongly filtered by SNP thresholds

Because the INDEL-specific (lenient) filters were no-ops, all filters applied uniformly:
- **163 INDELs** wrongly failed SNP-strict thresholds (SOR > 3.0, MQ < 40, FS > 60)
- INDEL PASS rate: 514/698 (73.6%) instead of expected ~677/698 (97.0%)

### Validation sensitivity loss

Ottilie Tier 2 truth set (343 mutations from Ottilie et al. 2022 Commun Biol 5:128):
- 1 truth INDEL (HygromycinB-36R8a XIV:572448 CTT>C, SOR=5.421) lost to `SOR_filter`
- GATK section [D] specifies **no SOR filter for INDELs** — this was a false positive

## Fix

### Config change (`conf/modules/joint_germline.config`)

Replace `TYPE==` with `vc.isSNP()` / `vc.isIndel()` and split filters per GATK [hard-filtering tutorial](https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering):

**Before:**
```groovy
// SNP filters applied to ALL variants (including INDELs)
'--filter-name "FS_filter" --filter "FS > 60.0"',
'--filter-name "SOR_filter" --filter "SOR > 3.0"',
'--filter-name "MQ_filter" --filter "MQ < 40.0"',
// INDEL filters (broken — TYPE== matches nothing)
'--filter-name "FS_INDEL_filter" --filter "TYPE==INDEL && FS > 200.0"',
'--filter-name "SOR_INDEL_filter" --filter "TYPE==INDEL && SOR > 10.0"',
```

**After:**
```groovy
// Universal (same for SNPs and INDELs)
'--filter-name "QD_filter" --filter "QD < 2.0"',
'--filter-name "QUAL_filter" --filter "QUAL < 30.0"',
// SNP-only (GATK section [C])
'--filter-name "FS_filter" --filter "vc.isSNP() && FS > 60.0"',
'--filter-name "SOR_filter" --filter "vc.isSNP() && SOR > 3.0"',
'--filter-name "MQ_filter" --filter "vc.isSNP() && MQ < 40.0"',
'--filter-name "MQRankSum_filter" --filter "vc.isSNP() && MQRankSum < -12.5"',
'--filter-name "ReadPosRankSum_filter" --filter "vc.isSNP() && ReadPosRankSum < -8.0"',
// INDEL-only (GATK section [D] — no SOR, MQ, MQRankSum)
'--filter-name "FS_INDEL_filter" --filter "vc.isIndel() && FS > 200.0"',
'--filter-name "ReadPosRankSum_INDEL_filter" --filter "vc.isIndel() && ReadPosRankSum < -20.0"'
```

Key changes:
- `vc.isSNP()` / `vc.isIndel()` replace broken `TYPE==` syntax
- SNP-only filters (FS, SOR, MQ, MQRankSum, ReadPosRankSum) no longer apply to INDELs
- Removed `SOR_INDEL_filter` — GATK section [D] has no SOR for INDELs
- QD and QUAL remain universal (same threshold for both types)

## Expected Results After Fix

| Metric | Before | After |
|--------|--------|-------|
| INDEL PASS rate | 514/698 (73.6%) | ~677/698 (97.0%) |
| Truth sensitivity (PASS only) | 332/343 (96.8%) | 333/343 (97.1%) |
| INDEL-specific filters firing | 0 (no-op) | Active |

## Spot-check Variants

| Position | Type | Current FILTER | Expected after fix |
|----------|------|---------------|-------------------|
| III:325 C>CA | INDEL | SOR_filter (SOR=3.12) | PASS |
| IV:1034111 ATG>A | INDEL | SOR_filter (SOR=3.13) | PASS |
| VIII:562551 TG>T | INDEL | MQ_filter;SOR_filter | PASS |
| XII:48855 C>CAAAA... | INDEL | FS_filter (FS=175.2) | PASS (FS<200) |
| III:322 A>C | SNP | SOR_filter (SOR=3.00) | SOR_filter (unchanged) |
| XV:60240 C>T | SNP | PASS (SOR=2.93) | PASS (unchanged) |

Verification script: `docs/variant-calling/haplotypecaller/verify_soft_filter_fix.sh`

## References

- GATK hard-filtering tutorial: https://gatk.broadinstitute.org/hc/en-us/articles/360035531112
- GATK JEXL expressions: https://gatk.broadinstitute.org/hc/en-us/articles/360035891011
- Ottilie et al. (2022) Commun Biol 5:128 — truth set source
