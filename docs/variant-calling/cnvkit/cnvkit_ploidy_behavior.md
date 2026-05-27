# CNVKit Ploidy Behavior in VCF Export

## Summary

CNVKit uses ploidy at two stages: `cnvkit.py call` and `cnvkit.py export vcf`. The pipeline currently uses the **nf-core/sarek 3.5.1 defaults** — no explicit `--ploidy` flag is passed, so both stages default to `--ploidy 2` (diploid). This is intentional; see "Ploidy Configuration History" below.

## Ploidy Configuration History

### April 2026: Added `--ploidy ${meta.ploidy}`

Added `--ploidy ${meta.ploidy}` to `CNVKIT_CALL` and `CNVKIT_EXPORT` to pass biological ploidy from the samplesheet.

### May 2026: Reverted to nf-core/sarek defaults (no `--ploidy`)

**Problem**: Passing `--ploidy 1` for haploid samples caused CNVKit VCF export to emit 18-22 **false DUP records** per sample — every baseline cn=2 segment was emitted as a DUP because cn=2 > ploidy=1. See `04_validate/cnvkit_ploidy_experiment/ploidy_comparison.md` for experiment results.

**Root cause**: CNVKit's CN scale always uses cn=2 as baseline regardless of `--ploidy` (the flat reference and default thresholds are ploidy-agnostic). Passing `--ploidy 1` misaligns the VCF export with the CN scale. See `cnvkit_ploidy_cn_scale.md`.

**Decision**: Revert to nf-core/sarek 3.5.1 defaults — remove all explicit `--ploidy` flags, letting cnvkit default to `--ploidy 2`. This aligns VCF export with the diploid CN scale and produces clean output (only real CNVs emitted).

```groovy
// Current (reverted to upstream defaults):
// CNVKIT_CALL: no ext.args (defaults to --ploidy 2)
// CNVKIT_CALL germline: ext.args = "--filter ci" (defaults to --ploidy 2)
// CNVKIT_EXPORT: ext.args = "vcf" (defaults to --ploidy 2)
```

**Trade-off**: The VCF uses diploid ploidy for all samples, which is technically incorrect for haploid samples but produces correct CN values on the diploid scale. For biological interpretation, use continuous CN from `.cnr` data: `absolute_cn = ploidy × 2^log2`. See `cnvkit_cn_calculation.md`.

## How Ploidy Flows Through CNVKit

| Pipeline Step | Config Location | Ploidy Used? | Command |
|---------------|----------------|--------------|---------|
| `cnvkit.py batch` | `cnvkit.config:19` | No | Correct - batch doesn't accept `--ploidy` |
| `cnvkit.py call` (germline) | `cnvkit.config:37` | No (defaults to 2) | `--filter ci` |
| `cnvkit.py call` (generic) | `cnvkit.config:28` | No (defaults to 2) | No ext.args |
| `cnvkit.py export vcf` | `cnvkit.config:48` | No (defaults to 2) | `vcf` |

## VCF Genotype Encoding (GT Field)

CNVKit's `export vcf` always uses **diploid-style GT notation** (`0/1`, `1/1`) regardless of the `--ploidy` setting. This is a CNVKit design choice, not a bug.

### GT Mapping for Structural Variants

| CN relative to ploidy | SVTYPE | GT | Meaning |
|------------------------|--------|-----|---------|
| CN = ploidy | - | Not emitted | Normal copy number |
| CN > ploidy | `<DUP>` | `0/1` | Copy number gain |
| 0 < CN < ploidy | `<DEL>` | `0/1` (diploid) or `1/1` (haploid) | Partial loss |
| CN = 0 | `<DEL>` | `1/1` | Complete loss |

### Effect of `--ploidy` on Output

**Current pipeline setting: `--ploidy 2` (default for all samples)**

- Baseline CN = 2 (matches CNVKit's internal CN scale)
- CN=0 → `<DEL>` with `1/1` (homozygous deletion)
- CN=1 → `<DEL>` with `0/1` (heterozygous deletion)
- CN=3 → `<DUP>` with `0/1` and `CN:3` (duplication)
- CN=2 → not emitted (baseline, correct)

**Why not `--ploidy 1` for haploid samples?**

Passing `--ploidy 1` to haploid samples causes every baseline cn=2 segment to be emitted as a false DUP (cn=2 > ploidy=1). This is because CNVKit's CN scale is always diploid — cn=2 is normal, regardless of biological ploidy. Aligning the VCF export with the CN scale (`--ploidy 2`) avoids this artifact.

### Example: Haploid Sample with `--ploidy 2` (current)

```
chr2   <DEL>  FOLD_CHANGE=0.22  GT:GQ  1/1:164    # CN=0, real loss
chr6   <DUP>  FOLD_CHANGE=1.42  GT:GQ:CN:CNQ  0/1:0:3:56  # CN=3, real gain
chr9   <DUP>  FOLD_CHANGE=1.21  GT:GQ:CN:CNQ  0/1:0:3:92  # CN=3, real gain
```

With `--ploidy 1` (previous, problematic):
```
chr1   <DUP>  ...  0/1:0:2:...   # FALSE DUP — cn=2 is baseline, not a gain
chr3   <DUP>  ...  0/1:0:2:...   # FALSE DUP — cn=2 is baseline
chr6   <DUP>  ...  0/1:0:3:...   # Real gain
# ... 18-22 false DUPs per sample
```

## Important Notes

1. **Always use the `CN` field** for downstream analysis rather than relying on GT encoding. CN gives the actual integer copy number.

2. **The `0/1` GT for DUP events** does not mean "heterozygous" in the SNP sense. It is the standard SV-VCF convention for representing a copy number gain.

3. **Fold change interpretation** depends on ploidy. The same log2 ratio maps to different CN values at different ploidies. Since we use `--ploidy 2` for all samples, interpret CN on the diploid scale and convert to absolute CN using `cn - 2 + ploidy`.

4. **Cache invalidation**: When changing `ext.args` in the config, old Nextflow cached results for `CNVKIT_EXPORT` must be cleared or the pipeline run without `-resume` to pick up the new parameter.

## Known Limitation: CN Scale Does Not Reflect Ploidy

The `cn` column in `.call.cns` always uses **cn=2 as baseline** regardless of `--ploidy`, because:
1. `cnvkit.py batch` builds a flat reference without ploidy awareness
2. The default thresholds (`-1.1,-0.25,0.2,0.7`) map log2≈0 to cn=2 for all ploidies
3. `--ploidy` only affects the overflow region (log2>0.7) and VCF export

For haploid samples: cn=2 = normal, cn=3 = duplication, cn=1 = deletion.

See `cnvkit_ploidy_cn_scale.md` for the full investigation and source code analysis.

## Files

- `conf/modules/cnvkit.config` (CNVKIT_CALL and CNVKIT_EXPORT — reverted to upstream defaults May 2026)
- Related: `cnvkit_ploidy_cn_scale.md`, `cnvkit_sarek_dual_call.md`, `cnvkit_cn_calculation.md`
