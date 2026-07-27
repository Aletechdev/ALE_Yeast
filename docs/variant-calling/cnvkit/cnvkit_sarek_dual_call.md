# CNVKit dual call: `.call.cns` vs `.germline.call.cns`

Why nf-core/sarek runs `cnvkit.py call` twice, producing two different call files per sample, and which
to use. Grounded in [`conf/modules/cnvkit.config`](../../../conf/modules/cnvkit.config) and
[`subworkflows/local/bam_variant_calling_cnvkit/main.nf`](../../../subworkflows/local/bam_variant_calling_cnvkit/main.nf).

## Output files

Per sample, CNVKit produces four `.cns` files:

| File | Producer | Key columns |
|------|----------|-------------|
| `.md.cns` | `cnvkit.py batch` → segment | log2, depth, ci_lo, ci_hi |
| `.md.call.cns` | `cnvkit.py batch` **internal** call | log2 (re-centered), cn, depth, **p_ttest** |
| `.md.germline.call.cns` | `CNVKIT_CALL` process (`--filter ci`) | log2 (original), cn, depth |
| `.md.bintest.cns` | `cnvkit.py batch` → bintest | bin-level significance |

## Why two call steps

**Step 1 — `cnvkit.py batch` internal call → `.md.call.cns`.** The full batch pipeline
(`coverage → fix → center_all → segment → call`) includes an internal call, giving:
- **re-centered log2** (median autosome shifted to exactly 0, ~0.03 shift),
- **`p_ttest`** (per-segment significance vs baseline),
- merged adjacent same-CN segments.

**Step 2 — `CNVKIT_CALL` process → `.md.germline.call.cns`.** Sarek then runs `cnvkit.py call` again on
the raw `.md.cns`, with `ext.args = "--filter ci"` ([`cnvkit.config:36-38`](../../../conf/modules/cnvkit.config#L36)).
No explicit `--ploidy` → defaults to `--ploidy 2`, matching the diploid CN scale (see
[`cnvkit_ploidy_behavior.md`](cnvkit_ploidy_behavior.md) for why `--ploidy ${meta.ploidy}` was reverted).
This gives:
- **original log2** (no re-centering),
- **CI filtering** — segments whose confidence interval spans zero are reset to baseline `cn`,
- **no `p_ttest`** (not computed by standalone `call`).

**Rationale for `--filter ci` on the germline path:** germline CNVs affect all cells and should be
high-confidence, so CI-resetting ambiguous segments reduces false positives; skipping re-centering also
avoids threshold-boundary flips. The exported VCF is produced from `.germline.call.cns`, so CI-filtered
input yields cleaner VCFs.

## The one residual difference (post ploidy-revert)

After the May 2026 ploidy revert (both files default to `--ploidy 2`), the two files agree on almost
everything; the sole systematic difference is the **~0.03 log2 re-centering shift** in `.md.call.cns`,
which can flip a borderline segment across the `0.2` gain threshold (e.g. `log2 = 0.187 → cn=2` in
`.call.cns` vs `0.217 → cn=3` in `.germline.call.cns`). High-CN overflow now matches between the files
because both use `ceil(2 × 2^log2)`.

## Which file to use — dual-matrix approach (recommended for ALE)

[`build_cn_matrix.py`](../../../bin/build_cn_matrix.py) builds **both** segment matrices plus a
disagreement report (`cn_call_vs_germline.csv`), so you can choose empirically against a truth set:

| Matrix | Source | Strengths | Weaknesses |
|--------|--------|-----------|------------|
| **Sensitive** | `.md.call.cns` | re-centered log2, `p_ttest`, all segments retained | may include low-confidence calls |
| **Stringent** | `.md.germline.call.cns` | CI-filtered (cleaner), matches VCF | no `p_ttest`, may miss weak-but-real signals |

Guidance:
- Clonal samples (strong signal) usually agree in both → either works; prefer stringent (simpler).
- Mixed-population/mosaic samples are where it matters → sensitive + `p_ttest` filtering preserves weak
  subclonal signals the stringent matrix may reset.

| Use case | File |
|----------|------|
| CN matrix (sensitive) | `.md.call.cns` |
| CN matrix (stringent) | `.md.germline.call.cns` |
| VCF export | `.md.germline.call.cns` |
| Continuous CN / heatmaps | `.md.cnr` (bin-level `fold_change`) |

## Files

- Pipeline config: [`conf/modules/cnvkit.config`](../../../conf/modules/cnvkit.config)
- Subworkflow: [`subworkflows/local/bam_variant_calling_cnvkit/main.nf`](../../../subworkflows/local/bam_variant_calling_cnvkit/main.nf)
- CN matrices / `fold_change`: [`cnvkit_cn_calculation.md`](cnvkit_cn_calculation.md)
- Ploidy & VCF export: [`cnvkit_ploidy_behavior.md`](cnvkit_ploidy_behavior.md)
