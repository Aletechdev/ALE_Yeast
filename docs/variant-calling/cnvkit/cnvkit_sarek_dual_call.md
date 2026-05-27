# CNVKit Sarek Dual Call Design: `.call.cns` vs `.germline.call.cns`

**Date**: 2026-05-23
**Context**: Understanding why nf-core/sarek runs `cnvkit.py call` twice, producing two different `.call.cns` files

## Output File Naming

CNVKit in sarek produces four `.cns` files per sample. Using `CBR110-15-R3a` as example:

| File | Full name | Producer | Key columns |
|------|-----------|----------|-------------|
| **`.md.cns`** | `CBR110-15-R3a.md.cns` | `cnvkit.py batch` → segment | log2, depth, ci_lo, ci_hi |
| **`.md.call.cns`** | `CBR110-15-R3a.md.call.cns` | `cnvkit.py batch` → internal call | log2 (re-centered), cn, depth, **p_ttest** |
| **`.md.germline.call.cns`** | `CBR110-15-R3a.md.germline.call.cns` | `CNVKIT_CALL` process (`--filter ci`) | log2 (original), cn, depth |
| **`.md.bintest.cns`** | `CBR110-15-R3a.md.bintest.cns` | `cnvkit.py batch` → bintest | Bin-level significance |

## Why Two Call Steps?

### Step 1: `cnvkit.py batch` internal call

`cnvkit.py batch` runs the full pipeline including an internal `call()`:

```
coverage → fix → center_all → segment → call → .call.cns
```

This produces `.md.call.cns` with:
- **Re-centered log2**: median autosome log2 shifted to exactly 0 (typically ~0.03 shift)
- **p_ttest**: statistical significance of each segment vs baseline
- **Merged segments**: adjacent same-CN segments combined (e.g., 22 → 20 segments)

### Step 2: `CNVKIT_CALL` process (sarek's separate Nextflow step)

Sarek then runs `cnvkit.py call` again as a separate process, taking the raw `.md.cns` as input:

```groovy
// subworkflows/local/bam_variant_calling_cnvkit/main.nf:31
CNVKIT_CALL(CNVKIT_BATCH.out.cns.map{ meta, cns -> [meta, cns[2], []]})
```

With germline config override (`conf/modules/cnvkit.config:36-38`):
```groovy
ext.args = "--filter ci"
```
Note: No explicit `--ploidy` is passed — cnvkit defaults to `--ploidy 2`, which matches the diploid CN scale. See `cnvkit_ploidy_behavior.md` for why `--ploidy ${meta.ploidy}` was reverted.

This produces `.md.germline.call.cns` with:
- **Original log2**: no re-centering (uses raw segmented values)
- **CI filtering**: segments where confidence interval spans zero may get CN reset to baseline
- **No p_ttest**: not computed by standalone `cnvkit.py call`

## Likely Rationale: Noise Reduction for Germline Calling

The sarek developers likely chose `--filter ci` for the germline path to reduce false positive CN calls. The reasoning:

1. **Germline CNVs should be high-confidence**: Unlike somatic/mosaic events, germline CNVs affect all cells and produce strong signal. A segment whose CI spans zero is likely noise, not a real germline event.

2. **CI filtering is conservative**: It only resets ambiguous segments to baseline CN — it doesn't remove segments or change high-confidence calls.

3. **Re-centering trade-off**: The batch internal call re-centers log2 (shifting ~0.03), which can push borderline segments across thresholds. By skipping re-centering, the germline path avoids these threshold-boundary artifacts.

4. **VCF export downstream**: The VCF is exported from `.germline.call.cns`, so CI-filtered output produces cleaner VCFs for downstream annotation.

## Practical Impact

### CN call differences (Ottilie pilot, 4 samples)

**Post-revert data (May 2026, `--ploidy 2` for both files):**

| Sample | `.call.cns` segments | `.germline.call.cns` segments | CN differences |
|--------|---------------------|------------------------------|----------------|
| CBR110-15-R3a | 20 | 20 | **chr VI**: cn=2 vs cn=3 (re-centering flips threshold) |
| Carmaphycin-R9-2 | 19 | 19 | Identical (cn=13 and cn=4 now agree) |
| Doxorubicin16-R2b | 18 | 18 | Identical (cn=13 now agrees) |
| NODRUG-GM2 | 17 | 17 | Identical |

### CBR110-15-R3a chr VI: Re-centering flips CN

```
.call.cns:              log2=0.187  → cn=2  (below 0.2 threshold)
.germline.call.cns:     log2=0.217  → cn=3  (above 0.2 threshold)
```

The ~0.03 re-centering shift pushed chr VI below the gain threshold in `.call.cns`. The `.germline.call.cns` (no re-centering) calls it as a gain. This is the only CN disagreement across all 4 pilot samples after the ploidy revert.

### Carmaphycin chr XII: High-CN now agrees after ploidy revert

```
.call.cns (re-centered):   log2=2.587 → cn=13  (ceil(2 × 2^2.587) = ceil(12.03))
.germline.call.cns:         log2=2.586 → cn=13  (ceil(2 × 2^2.586) = ceil(12.02))
```

Previously with `--ploidy 1` in `CNVKIT_CALL`, `.germline.call.cns` reported cn=7 (`ceil(1 × 2^2.586)`). After reverting to `--ploidy 2`, both files use the same overflow formula and agree on cn=13.

### Carmaphycin chr XII:1063202-1078177: Small segment also agrees

```
.call.cns:              log2=0.774  → cn=4  (ceil(2 × 2^0.774) = ceil(3.42))
.germline.call.cns:     log2=0.773  → cn=4  (ceil(2 × 2^0.773) = ceil(3.41))
```

Previously cn=2 in `.germline.call.cns` due to either CI filter reset or ploidy=1 effect. With `--ploidy 2`, both agree on cn=4. This 3-probe segment is low confidence but now consistent.

## Which File to Use

### Dual-Matrix Approach (Recommended for ALE)

Generate **both** segment-level CN matrices and compare empirically before committing to one:

| Matrix | Source | Strengths | Weaknesses |
|--------|--------|-----------|------------|
| **Sensitive matrix** | `.md.call.cns` | Re-centered log2, has `p_ttest`, all segments retained | May include low-confidence calls |
| **Stringent matrix** | `.md.germline.call.cns` | CI-filtered (cleaner), matches VCF | No `p_ttest`, may miss weak-but-real signals |

**Naming rationale for ALE**:
- **Sensitive**: Retains all CN segments including weak signals from subclonal or mosaic events common in mixed-population ALE. Includes statistical confidence (`p_ttest`) for downstream filtering at user-defined thresholds.
- **Stringent**: Only segments where the confidence interval does not span the baseline. Better for clonal ALE samples where real CNVs produce strong, unambiguous signal.

**Decision criteria**:
- If both agree on known CNVs and disagreements are all noise → use stringent (simpler)
- If stringent misses real mosaic/subclonal events → use sensitive + p_ttest filtering
- Clonal vs mixed-population samples may warrant different modes

### Per-use-case summary

| Use case | File | Why |
|----------|------|-----|
| **CN matrix (sensitive)** | `.md.call.cns` | Re-centered, p_ttest for user-controlled filtering |
| **CN matrix (stringent)** | `.md.germline.call.cns` | CI-filtered, fewer false positives |
| **VCF export** | `.md.germline.call.cns` | Used by sarek pipeline |
| **Continuous CN / heatmaps** | `.md.cnr` | Bin-level, uniform across samples, `ploidy × 2^log2` |

## ✅ Ploidy Reverted to Defaults (May 2026)

`CNVKIT_CALL` and `CNVKIT_EXPORT` no longer pass explicit `--ploidy` — both default to `--ploidy 2`, matching the diploid CN scale:

- **`.md.call.cns`**: Unchanged (batch always uses ploidy=2 internally)
- **`.md.germline.call.cns`**: High-CN overflow formula now uses `ceil(2 × 2^log2)`, matching `.call.cns`
- **VCF**: Baseline segments (cn=2) correctly hidden instead of emitted as false DUPs
- **Remaining difference**: Re-centering (~0.03 log2 shift) between the two files
- **Carmaphycin chr XII** (verified): Both files now produce cn=13 for log2≈2.59 and cn=4 for log2≈0.77 (previously `.germline.call.cns` reported cn=7 and cn=2 with `--ploidy 1`)

## Files

- Pipeline config: `conf/modules/cnvkit.config`
- Subworkflow: `subworkflows/local/bam_variant_calling_cnvkit/main.nf`
- CN calculation formulas: `docs/variant-calling/cnvkit/cnvkit_cn_calculation.md`
- Ploidy CN scale: `docs/variant-calling/cnvkit/cnvkit_ploidy_cn_scale.md`
- Ploidy VCF export: `docs/variant-calling/cnvkit/cnvkit_ploidy_behavior.md`