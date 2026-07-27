# CNVKit CN Matrices — `fold_change` reference

**Canonical reference** for the multi-sample copy-number matrices built from CNVKit output for ALE
analysis. Describes what the matrix scripts actually emit; grounded in
[`bin/build_cn_matrix.py`](../../../bin/build_cn_matrix.py) and
[`bin/cn_cohort_matrix.py`](../../../bin/cn_cohort_matrix.py).

> **History:** earlier revisions of this doc recommended `absolute_cn = ploidy × 2^log2` and an integer
> `cn − 2 + ploidy`. Both are **gone from the code** — the matrices now emit a single ploidy-agnostic
> `fold_change`. Rationale below; the old ploidy-scale investigation is archived at
> [`docs/archive/cnvkit/cnvkit_ploidy_cn_scale.md`](../../archive/cnvkit/cnvkit_ploidy_cn_scale.md).

## The metric: `fold_change = 2^log2`

Every matrix column is derived from CNVKit's `log2` (the GC-corrected, centered
`log2(sample_depth / reference_depth)` — see *Derivation* below):

```python
fold_change = 2 ** log2          # bin- or segment-level, continuous (never rounded)
```

| `fold_change` | Meaning |
|---------------|---------|
| `1.0` | same depth as the reference baseline |
| `> 1` | copy-number **gain** |
| `< 1` | copy-number **loss** |

**Why `fold_change`, not `absolute_cn`:** it is the direct depth ratio — ploidy-agnostic, so it is
comparable across samples of *different* ploidy, and it needs no assumption CNVKit doesn't make.
CNVKit's integer `cn` always uses **`cn = 2` as baseline regardless of `--ploidy`** (its flat reference
and default thresholds are ploidy-agnostic — see
[`cnvkit_ploidy_behavior.md`](cnvkit_ploidy_behavior.md)), so an `absolute_cn = ploidy × 2^log2`
column implied a precision the tool doesn't provide and misled on haploid samples. Keeping the raw
`log2` **and** its `fold_change` means CN can always be re-interpreted downstream without re-running
CNVKit.

Each matrix therefore carries **two paired columns per sample**: `{sample}_log2` (raw signal) and
`{sample}_fold_change` (`2^log2`).

## Source files and the three matrix types

`build_cn_matrix.py` reads three CNVKit outputs per sample and produces:

| Output CSV | Source | Notes |
|------------|--------|-------|
| `cn_segments_call.csv` | `.md.call.cns` | per-segment; re-centered log2; has `p_ttest` (sensitive) |
| `cn_segments_germline.csv` | `.md.germline.call.cns` | per-segment; CI-filtered; no `p_ttest` (stringent) |
| `cn_chr_summary_call.csv` | `.md.call.cns` | one row per chromosome (dominant = largest-span segment) |
| `cn_chr_summary_germline.csv` | `.md.germline.call.cns` | one row per chromosome |
| `cn_call_vs_germline.csv` | both | rows where call vs germline `fold_change` differ by > 0.1 (only written if any) |
| `cn_bins_continuous.csv` | `.md.cnr` | bin-level (~5 kb), all samples share identical bin coords → directly stackable |

Segment CSV columns: `sample, chromosome, start, end, log2, fold_change, depth, probes[, p_ttest]`.
Chr-summary / bins CSV columns: coords + `{sample}_log2, {sample}_fold_change` per sample.

### Dual "call" vs "germline" matrices

The two segment sources come from CNVKit being called twice (a sarek design point — full detail in
[`cnvkit_sarek_dual_call.md`](cnvkit_sarek_dual_call.md)):

- **`.md.call.cns`** (sensitive): `cnvkit.py batch`'s internal call — re-centered log2, retains all
  segments, includes `p_ttest` for user-controlled filtering. Best for mixed-population/mosaic ALE
  samples where weak subclonal signals matter.
- **`.md.germline.call.cns`** (stringent): the separate `CNVKIT_CALL --filter ci` step — CI-filtered
  (ambiguous segments reset to baseline), matches the exported VCF. Best for clonal samples with strong
  signal.

`cn_call_vs_germline.csv` reports where they disagree so you can pick empirically against a truth set.

### Bin-level `.cnr` matrix

`.md.cnr` bins are uniform (~5 kb) and identical across samples, so they stack into a samples × bins
matrix with no breakpoint merging. Continuous `fold_change` preserves fractional (subclonal/mosaic)
signal — best for heatmaps and clustering.

## Cohort collapse (`cn_cohort_matrix.py --collapse`)

The bin matrix is large and mostly baseline. `cn_cohort_matrix.py` optionally collapses it:

1. **Drop baseline bins** — a bin is baseline if **all** samples have `|log2| < 0.3` (`fold_change`
   ≈ 0.81–1.23); such bins are removed.
2. **Merge adjacent survivors** — consecutive non-baseline bins on the same chromosome
   (`row.start == prev.end`) merge into one region.

**Jensen's-inequality fix (important):** on merge, `log2` is averaged and `fold_change` is
**re-derived** as `2^avg_log2` — *not* averaged directly, because `mean(2^x) ≠ 2^mean(x)`
([`cn_cohort_matrix.py:74`](../../../bin/cn_cohort_matrix.py)). Averaging `fold_change` would bias the
merged value upward.

With `--fai`, a `chr_length` column is added for genomic context.

## Derivation (why `2^log2` is the depth ratio)

CNVKit's per-sample pipeline:

```
coverage → fix() [log2(sample/reference), GC-correct] → center_all() [median autosome log2 → 0]
         → segment() [CBS] → call() [threshold log2 → integer cn]
```

After centering, `log2 = 0` means "same depth as the median autosome" (the baseline), so
`2^log2 = sample_depth / median_depth` — the copy ratio relative to the reference. That ratio *is*
`fold_change`; multiplying by a ploidy to get "absolute CN" only holds under a clean-diploid assumption
CNVKit's flat reference doesn't encode.

## Files

- Scripts: [`bin/build_cn_matrix.py`](../../../bin/build_cn_matrix.py),
  [`bin/cn_cohort_matrix.py`](../../../bin/cn_cohort_matrix.py)
- Pipeline config: [`conf/modules/cnvkit.config`](../../../conf/modules/cnvkit.config)
- Dual call design: [`cnvkit_sarek_dual_call.md`](cnvkit_sarek_dual_call.md)
- Ploidy & VCF export: [`cnvkit_ploidy_behavior.md`](cnvkit_ploidy_behavior.md)
- Small-chromosome exclusion: [`cnvkit_small_chr_exclusion.md`](cnvkit_small_chr_exclusion.md)
- Archived ploidy-scale investigation: [`docs/archive/cnvkit/cnvkit_ploidy_cn_scale.md`](../../archive/cnvkit/cnvkit_ploidy_cn_scale.md)
