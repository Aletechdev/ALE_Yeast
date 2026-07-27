# CNVKit — Ploidy & VCF export

How ploidy flows (or doesn't) through CNVKit, why the pipeline passes **no** explicit `--ploidy`, and
how to read the exported VCF. Grounded in [`conf/modules/cnvkit.config`](../../../conf/modules/cnvkit.config).

## TL;DR

- The pipeline uses **nf-core/sarek defaults — no `--ploidy` flag** → CNVKit defaults to `--ploidy 2`
  everywhere. This is deliberate (see history below).
- CNVKit's CN scale **always uses `cn = 2` as baseline regardless of `--ploidy`**. So for a haploid
  sample too: `cn=2` = normal, `cn=3` = gain, `cn=1` = loss.
- For biological interpretation, prefer the continuous **`fold_change = 2^log2`** from `.cnr`/segment
  data (see [`cnvkit_cn_calculation.md`](cnvkit_cn_calculation.md)), not the integer `cn`.

## Ploidy configuration history

**April 2026 — added `--ploidy ${meta.ploidy}`** to `CNVKIT_CALL` and `CNVKIT_EXPORT` to pass biological
ploidy from the samplesheet.

**May 2026 — reverted to sarek defaults (no `--ploidy`).** Passing `--ploidy 1` for haploid samples made
`export vcf` emit **18–22 false DUP records** per sample: every baseline `cn=2` segment became a DUP
because `cn=2 > ploidy=1`. Root cause: CNVKit's CN scale is always diploid-baseline, so `--ploidy 1`
misaligns the VCF export with the scale. Reverting (default `--ploidy 2`) aligns export with the scale
and yields clean output (only real CNVs emitted).

```groovy
// Current (conf/modules/cnvkit.config) — reverted to upstream defaults:
// CNVKIT_BATCH:  --method wgs/hybrid (batch does not accept --ploidy)
// CNVKIT_CALL (germline): ext.args = "--filter ci"   → defaults to --ploidy 2
// CNVKIT_CALL (generic):  no ext.args                → defaults to --ploidy 2
// CNVKIT_EXPORT:          ext.args = "vcf"           → defaults to --ploidy 2
```

## How ploidy flows through CNVKit

| Step | Config | `--ploidy`? | Command |
|------|--------|-------------|---------|
| `cnvkit.py batch` | `cnvkit.config:19` | not accepted | `--method wgs/hybrid --diagram --scatter` |
| `cnvkit.py call` (germline) | `cnvkit.config:37` | default 2 | `--filter ci` |
| `cnvkit.py call` (generic) | `cnvkit.config:28` | default 2 | *(none)* |
| `cnvkit.py export vcf` | `cnvkit.config:48` | default 2 | `vcf` |

### What `--ploidy` actually changes (and doesn't)

`cnvkit.py call --ploidy N`:

| Behavior | Affected by `--ploidy`? |
|----------|-------------------------|
| Threshold-based CN (`log2 ≤ 0.7`) | **No** — same mapping for all ploidies |
| Overflow CN (`log2 > 0.7`) | **Yes** — `cn = ceil(ploidy × 2^log2)` |
| Sex-chromosome `ref_copies` | **Yes** — `ploidy // 2` |
| Centering / log2 scale | **No** |

`cnvkit.py export vcf --ploidy N`: **Yes** to which CN values emit a record (`CN ≠ ploidy`), SVTYPE
(`CN > ploidy` → DUP, `< ploidy` → DEL), and GT encoding. `cnvkit.py batch`: no `--ploidy` — the flat
reference is always ploidy-agnostic.

## Why the CN scale is always `cn = 2` baseline

1. `cnvkit.py batch --method wgs` builds a **flat reference** (`log2 = 0`, `depth = 1` for all bins) —
   no ploidy concept.
2. `log2` is **depth-relative, not ploidy-relative**: `fix()` computes `log2(sample/reference)`, then
   `center_all()` shifts the median autosome to `log2 = 0`.
3. The **default thresholds are diploid** and map the common range independent of ploidy:

   ```
   thresholds: -1.1, -0.25, 0.2, 0.7
     log2 ≤ -1.1          → cn=0
     -1.1 < log2 ≤ -0.25  → cn=1
     -0.25 < log2 ≤ 0.2   → cn=2   ← baseline (log2 ≈ 0 lands here)
     0.2 < log2 ≤ 0.7     → cn=3
     log2 > 0.7           → cn = ceil(ref_copies × 2^log2)
   ```

`--ploidy` only touches the overflow region (`log2 > 0.7`), sex chromosomes, and VCF export — never the
common-range threshold mapping. **Custom `-t` thresholds don't fix this**: they assume ploidy-relative
`log2(cn/ploidy)`, but the values are reference-relative `log2(sample/median)`. Full source-code
investigation: [archived ploidy-scale notes](../../archive/cnvkit/cnvkit_ploidy_cn_scale.md).

### Interpreting the integer `cn` (any ploidy)

| `cn` in `.call.cns` | Meaning |
|---------------------|---------|
| 0 | deep deletion (complete loss) |
| 1 | single-copy loss vs baseline |
| **2** | **baseline / normal** |
| 3 | single-copy gain |
| 4+ | high-level amplification |

The `log2`/`fold_change` columns are more informative than `cn` for actual copy-number change.

## VCF export (GT encoding)

`cnvkit.py export vcf` always uses **diploid-style GT** (`0/1`, `1/1`) regardless of `--ploidy` — a
CNVKit design choice, not a bug.

| CN vs ploidy | SVTYPE | GT | Meaning |
|--------------|--------|-----|---------|
| CN = ploidy | — | not emitted | normal |
| CN > ploidy | `<DUP>` | `0/1` | copy-number gain |
| 0 < CN < ploidy | `<DEL>` | `0/1` (diploid) / `1/1` (haploid) | partial loss |
| CN = 0 | `<DEL>` | `1/1` | complete loss |

Example (haploid sample, current `--ploidy 2` default — clean):

```
chr2   <DEL>  FOLD_CHANGE=0.22  GT:GQ         1/1:164       # CN=0, real loss
chr6   <DUP>  FOLD_CHANGE=1.42  GT:GQ:CN:CNQ  0/1:0:3:56    # CN=3, real gain
```

**Notes:**
1. Use the **`CN` field** for downstream analysis, not the GT — `CN` is the actual integer copy number.
2. `0/1` for a `<DUP>` is the standard SV-VCF convention for a gain, **not** SNP-style heterozygosity.
3. **Cache invalidation:** changing `CNVKIT_EXPORT` `ext.args` requires clearing the Nextflow cache (or
   running without `-resume`) to pick up the new parameter.

## Files

- Pipeline config: [`conf/modules/cnvkit.config`](../../../conf/modules/cnvkit.config)
- CN matrices / `fold_change`: [`cnvkit_cn_calculation.md`](cnvkit_cn_calculation.md)
- Dual call design: [`cnvkit_sarek_dual_call.md`](cnvkit_sarek_dual_call.md)
- Archived ploidy-scale investigation (source-code analysis, custom-threshold experiment):
  [`docs/archive/cnvkit/cnvkit_ploidy_cn_scale.md`](../../archive/cnvkit/cnvkit_ploidy_cn_scale.md)
