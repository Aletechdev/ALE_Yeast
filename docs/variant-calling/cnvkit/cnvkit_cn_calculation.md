# CNVKit Absolute Copy Number Calculation

**Date**: 2026-05-23
**Context**: Multi-sample CN analysis for ALE experiments with non-diploid organisms

## Problem

CNVKit's integer CN values (`.call.cns`) use a **diploid scale** regardless of sample ploidy:
- cn=2 always means "baseline" (same as reference)
- `--ploidy` flag does not change the threshold-to-CN mapping (see `cnvkit_ploidy_cn_scale.md`)
- Rounding on a haploid scale loses subclonal/mosaic signals

### Example: CBR110-15-R3a Chr I whole-chromosome duplication

| Method | Value | `round(cn - 2 + ploidy)` | `round(ploidy × 2^log2)` |
|--------|-------|---------------------------|---------------------------|
| `.call.cns` | cn=3, log2=0.329 | **2** (correct) | — |
| `.cnr` bin-level | log2=0.329 | — | **round(1.26) = 1** (missed!) |

The duplication shows log2=0.33 (not the expected 1.0 for a clean 2×), likely due to population mosaicism (~30% of cells). On CNVKit's diploid scale, 2×2^0.33 = 2.51 → rounds to 3 (detected). On a haploid scale, 1×2^0.33 = 1.26 → rounds to 1 (missed).

## Recommended Formula

### For continuous CN (preferred for analysis)

```python
absolute_cn = ploidy * 2**log2
```

This is mathematically: `ploidy × (sample_depth / median_depth)`, which is the definition of absolute copy number.

**Keep values continuous** — do not round. Fractional CN reflects real biology:
- 1.26 copies = elevated signal, likely subclonal duplication
- 1.0 copies = normal haploid baseline
- 0.5 copies = partial deletion or mosaic loss

### For integer CN calls (when needed)

Use CNVKit's diploid-scale `cn` from `.call.cns` with post-hoc adjustment:

```python
absolute_cn = cn - 2 + ploidy
```

This preserves CNVKit's tuned thresholds (which catch noisy signals like log2=0.33 → cn=3) and shifts to the correct ploidy baseline.

**Do not use** `round(ploidy × 2^log2)` for integer calls — the rounding on a haploid scale is too aggressive for mosaic/subclonal events.

## Derivation

CNVKit's internal pipeline:

```
1. coverage(sample) → raw depth per ~5kb bin
2. fix() → log2(sample_depth / reference_depth), GC correction
3. center_all() → shift so median autosome log2 = 0
4. segment() → CBS segmentation → .cns
5. call() → threshold log2 → integer CN → .call.cns
```

After step 3, `log2 = 0` means "same depth as median autosome". The median autosome represents the baseline ploidy. Therefore:

```
2^log2 = sample_depth / median_depth = relative copy ratio
ploidy × 2^log2 = absolute copy number
```

### Why `cn - 2 + ploidy` works for integers

CNVKit maps log2≈0 → cn=2 (diploid baseline). The shift `- 2 + ploidy` converts from diploid baseline to true ploidy baseline:

| `.call.cns` cn | Diploid meaning | Haploid absolute (`cn - 2 + 1`) | Diploid absolute (`cn - 2 + 2`) |
|----------------|-----------------|----------------------------------|----------------------------------|
| 0 | Deep deletion | -1 → 0 (clamp) | 0 |
| 1 | Loss | 0 | 1 |
| 2 | Baseline | 1 | 2 |
| 3 | Gain | 2 | 3 |
| 4 | Amplification | 3 | 4 |

**Note**: cn=0 with ploidy=1 gives -1, which should be clamped to 0 (biological minimum).

## Multi-Sample CN Matrix

For comparing CN across samples, use `.cnr` files (bin-level, ~5kb resolution):

- **Bins are uniform and identical** across all samples — no breakpoint merging needed
- **Continuous signal** — `log2` per bin, not thresholded to integers
- **Directly stackable** into a samples × bins matrix

### Building the matrix

```python
# Per sample, per bin:
absolute_cn = ploidy * 2**log2  # continuous, keeps fractional signal

# Output: two paired columns per sample — log2 (raw signal) + absolute CN (interpreted)
# chrom, start, end, sample1_log2, sample1_cn, sample2_log2, sample2_cn, ...
```

### Why include both log2 and absolute CN

| Column | What it captures | Use case |
|--------|-----------------|----------|
| `log2` | Raw depth ratio, ploidy-agnostic | Comparable across ploidies, heatmaps, clustering, QC |
| `absolute_cn` | Biological copy number (`ploidy × 2^log2`) | Interpretation, reporting, CNV calling |

The `log2` ratio is the ground truth — it's the direct measurement before any ploidy assumption is applied. Keeping it in the output means:
- You can re-derive CN with a different ploidy without re-running CNVKit
- Cross-sample comparisons are valid even if samples have different ploidies
- Standard for CNV visualization tools (IGV, heatmaps use log2 scale)

### Comparison of source files

| Approach | Pros | Cons |
|----------|------|------|
| `.cnr` + `ploidy × 2^log2` | Uniform bins, continuous signal, no merging | Noisy (bin-level), no integer calls |
| `.md.call.cns` (batch internal) | Re-centered log2, has `p_ttest`, all segments retained | Different boundaries per sample, requires breakpoint merging |
| `.md.germline.call.cns` (sarek CNVKIT_CALL) | CI-filtered (cleaner), matches VCF output | No `p_ttest`, no re-centering, may silently drop weak-but-real signals |
| `.call.cns` `export seg` | Multi-sample in one file, IGV-compatible | Only log2 (no CN column), no ploidy adjustment |

### Dual-Matrix Strategy

Generate **two** segment-level CN matrices and compare empirically before choosing:

1. **Sensitive matrix** (from `.md.call.cns`):
   - Re-centered log2 (more accurate cross-sample baseline)
   - `p_ttest` included — filter at your own threshold
   - All segments retained — no silent CI-based resets
   - Retains weak signals from subclonal or mosaic events common in mixed-population ALE
   - Columns per sample: `log2`, `cn`, `absolute_cn` (`ploidy × 2^log2`), `p_ttest`

2. **Stringent matrix** (from `.md.germline.call.cns`):
   - CI-filtered — low-confidence segments reset to baseline CN
   - Matches what the VCF export uses
   - Better for clonal ALE samples where real CNVs produce strong, unambiguous signal
   - Columns per sample: `log2`, `cn`, `absolute_cn` (`ploidy × 2^log2`)

**Compare**: Where do the two matrices agree on known CNVs (e.g., chr I dup)? Where do they disagree? Check disagreements against truth set to determine which mode is better for ALE.

**Decision criteria**: Clonal samples (strong signal) should agree in both — if so, either works. Mixed-population/mosaic samples are where differences matter: the sensitive matrix preserves weak signals, the stringent matrix may miss them but has fewer false positives.

### Additional visualizations

- **For heatmaps/clustering**: Use `.cnr` continuous CN matrix (fractional values show subclonal events)
- **For IGV visualization**: Use `cnvkit.py export seg` (multi-sample, but log2 only)

See `docs/variant-calling/cnvkit/cnvkit_sarek_dual_call.md` for full comparison of the two call files with data from all 4 pilot samples.

## Files

- Ploidy CN scale investigation: `docs/variant-calling/cnvkit/cnvkit_ploidy_cn_scale.md`
- Ploidy VCF export behavior: `docs/variant-calling/cnvkit/cnvkit_ploidy_behavior.md`
- Sarek dual call design (`.call.cns` vs `.germline.call.cns`): `docs/variant-calling/cnvkit/cnvkit_sarek_dual_call.md`
- Ploidy experiment results: `docs/benchmarking/ottilie_xenobiotic_ale/04_validate/cnvkit_ploidy_experiment/`
- Pipeline config: `conf/modules/cnvkit.config`