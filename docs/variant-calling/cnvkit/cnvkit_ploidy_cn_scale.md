# CNVKit CN Scale vs Ploidy — Investigation Notes

**Date**: 2026-05-19
**Context**: Ottilie Tier 2 validation, haploid yeast (ploidy=1)

## Problem Statement

CNVKit's `.call.cns` output reports **cn=2 as baseline** for haploid samples, even when `--ploidy 1` is passed to `cnvkit.py call`. This means CN values do not represent absolute copy number — they represent a reference-relative scale.

## Root Cause

### 1. Flat reference has no ploidy concept

`cnvkit.py batch --method wgs` builds a flat reference (`reference.cnn`) with log2=0, depth=1 for all bins. No `--ploidy` flag is accepted. The reference is ploidy-agnostic.

### 2. Log2 ratios are depth-relative, not ploidy-relative

Per-sample processing in `batch`:
1. Coverage computed per ~5kb bin
2. `do_fix()`: log2(sample_depth / reference_depth), GC correction
3. `center_all(median)`: shifts so **median autosome log2 = 0**
4. Segmentation (CBS)
5. `do_call(method="threshold")`: maps log2 to integer CN using hardcoded thresholds

### 3. Default thresholds assume diploid scale

```
Thresholds: -1.1, -0.25, 0.2, 0.7

Mapping:
  log2 ≤ -1.1          → CN=0
  -1.1 < log2 ≤ -0.25  → CN=1
  -0.25 < log2 ≤ 0.2   → CN=2  ← baseline (log2≈0 lands here)
  0.2 < log2 ≤ 0.7     → CN=3
  log2 > 0.7            → CN=ceil(ref_copies × 2^log2)
```

The `--ploidy` flag only affects:
- The overflow formula for log2 > 0.7 (via `ref_copies`)
- Sex chromosome handling (`ref_copies = ploidy // 2` for chrY)
- VCF export (`cnvkit.py export vcf --ploidy`)

It does **NOT** change the threshold-to-CN mapping for the common range.

### 4. Custom thresholds failed

We attempted to compute ploidy-aware thresholds as midpoints between log2(n/P) and log2((n+1)/P):

| Ploidy | Computed thresholds |
|--------|-------------------|
| 1 | -1.00, 0.50, 1.29 |
| 2 | -2.00, -0.50, 0.29, 0.79 |
| 3 | -2.58, -1.08, -0.29, 0.21, 0.58 |

**Result**: For ploidy=1, all segments mapped to cn=1 (including true duplications). The thresholds assume log2 ratios are on a ploidy-relative scale (log2(CN/ploidy)), but they are actually on a **reference-relative** scale (log2(sample_depth/median_depth)).

### 5. Why the depth ratio is compressed

For CBR110-15R3a (known chr I whole-chromosome duplication):

| Source | Chr I depth | Median autosome | Ratio | log2 |
|--------|------------|-----------------|-------|------|
| CNVKit .cnr | 115.9 | 89.2 | 1.30 | 0.38 |
| samtools idxstats | 1252 reads/kb | 923 reads/kb | 1.36 | 0.44 |

Expected for clean 2-copy duplication: ratio=2.0, log2=1.0.

The actual ratio of ~1.3x suggests either:
- **Mosaicism**: ~36% of cells carry the duplication
- **Population heterogeneity**: Mixed clones from ALE evolution
- This is a biological reality, not a CNVKit artifact

Despite the compressed signal, CNVKit correctly detects it as a gain (log2=0.36 > 0.2 threshold → cn=3).

## What `--ploidy` Actually Does

### `cnvkit.py call --ploidy N`

| Behavior | Affected by --ploidy? |
|----------|----------------------|
| Threshold-based CN (log2 ≤ 0.7) | **No** — same mapping for all ploidies |
| Overflow CN (log2 > 0.7) | **Yes** — `CN = ceil(ploidy × 2^log2)` |
| Sex chromosome ref_copies | **Yes** — `ploidy // 2` |
| Centering / log2 scale | **No** |

### `cnvkit.py export vcf --ploidy N`

| Behavior | Affected by --ploidy? |
|----------|----------------------|
| Which CN values emit VCF records | **Yes** — CN ≠ ploidy emits a record |
| SVTYPE (DUP vs DEL) | **Yes** — CN > ploidy → DUP, CN < ploidy → DEL |
| GT field encoding | **Yes** — relative to ploidy baseline |

### `cnvkit.py batch`

No `--ploidy` flag accepted. Reference is always ploidy-agnostic.

## How to Interpret CN Values

For **any** ploidy with flat reference and default thresholds:

| CN in .call.cns | Meaning |
|-----------------|---------|
| cn=0 | Deep deletion (complete loss) |
| cn=1 | Single-copy loss relative to baseline |
| **cn=2** | **Baseline / normal** |
| cn=3 | Single-copy gain |
| cn=4+ | High-level amplification |

The `log2` and `depth` columns are more informative than `cn` for interpreting actual copy number changes.

## Recommendation for ALE Pipeline

### Current status: Acceptable for validation

The default thresholds correctly detect gains (cn>2) and losses (cn<2). For the Ottilie validation, this is sufficient to match against Sup Data 5 CNV events.

### For future improvement

Three options if absolute CN is needed:

1. **Continuous CN from `.cnr` log2** (preferred for analysis):
   ```python
   # Gives fractional CN — preserves subclonal/mosaic signals
   absolute_cn = ploidy * 2**log2  # e.g., log2=0.33, ploidy=1 → 1.26 copies
   ```
   Best for multi-sample heatmaps and clustering. Do not round — fractional values
   reflect real biology (mosaicism, population heterogeneity). See `cnvkit_cn_calculation.md`.

2. **Integer CN from `.call.cns`** (for variant calling/reporting):
   ```python
   # Uses CNVKit's tuned thresholds, then shifts to correct ploidy baseline
   absolute_cn = cn - 2 + ploidy  # e.g., cn=3, ploidy=1 → absolute=2
   ```
   Preserves sensitivity for noisy signals (e.g., log2=0.33 → cn=3 on diploid scale).
   Rounding `ploidy × 2^log2` directly loses these mosaic events on haploid scale.

3. **Build a normal-sample reference** instead of flat reference — pass the parent sample as `-n parent.bam` to `cnvkit.py batch`. This would make the log2 ratios relative to the parent's copy number profile. However, Sarek's CNVKit module may not support this easily for germline-only workflows.

### Not recommended

- Custom thresholds via `-t` — they assume ploidy-normalized log2 ratios which don't exist with flat references
- Removing `--ploidy` — it still affects VCF export and high-CN overflow calculations
- `round(ploidy × 2^log2)` for integer calls — too aggressive for mosaic signals on haploid scale (see `cnvkit_cn_calculation.md` for worked example)

## Files

- Pipeline config: `conf/modules/cnvkit.config`
- Ploidy VCF export docs: `docs/variant-calling/cnvkit/cnvkit_ploidy_behavior.md`
- CNVKit Docker image: `quay.io/biocontainers/cnvkit:0.9.10--pyhdfd78af_0`

## Source Code References (cnvkit 0.9.10)

- `cnvlib/batch.py:batch_run_sample()` — hardcodes `do_call(method="threshold")` with ploidy=2
- `cnvlib/call.py:absolute_threshold()` — threshold-to-CN mapping logic
- `cnvlib/call.py:_reference_copies_pure()` — ploidy → ref_copies for sex chroms
- `cnvlib/fix.py:load_adjust_coverages()` — `center_all()` normalizes log2 to median
- `cnvlib/reference.py:do_reference_flat()` — flat reference: log2=0 for all bins
