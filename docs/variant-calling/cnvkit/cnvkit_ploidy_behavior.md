# CNVKit Ploidy Behavior in VCF Export

## Summary

CNVKit uses ploidy at two stages: `cnvkit.py call` and `cnvkit.py export vcf`. Both must receive the correct `--ploidy` value for accurate results. The pipeline passes `meta.ploidy` from the samplesheet to both stages.

## Bug Fix (April 2026)

**Problem**: `cnvkit.py export vcf` was not receiving `--ploidy` from the pipeline. It defaulted to `--ploidy 2` (diploid), producing incorrect genotype representations for haploid samples.

**Symptom**: Haploid (ploidy=1) samples showed diploid-style heterozygous calls (`0/1`) for deletions that should have been complete losses.

**Fix**: Added `--ploidy ${meta.ploidy}` to `CNVKIT_EXPORT` in `conf/modules/cnvkit.config`:

```groovy
// Before (broken):
ext.args = "vcf"

// After (fixed):
ext.args = { "vcf --ploidy ${meta.ploidy}" }
```

## How Ploidy Flows Through CNVKit

| Pipeline Step | Config Location | Ploidy Used? | Command |
|---------------|----------------|--------------|---------|
| `cnvkit.py batch` | `cnvkit.config:19` | No | Correct - batch doesn't accept `--ploidy` |
| `cnvkit.py call` (germline) | `cnvkit.config:39` | Yes | `--filter ci --ploidy ${meta.ploidy}` |
| `cnvkit.py call` (generic) | `cnvkit.config:30` | Yes | `--ploidy ${meta.ploidy}` |
| `cnvkit.py export vcf` | `cnvkit.config:49` | Yes (fixed) | `vcf --ploidy ${meta.ploidy}` |

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

**Ploidy=1 (haploid):**
- Baseline CN = 1
- CN=0 → `<DEL>` with `1/1` (complete loss)
- CN=2 → `<DUP>` with `0/1` and `CN:2` (duplication)
- No heterozygous deletions (`0/1` DEL) — correct for haploid
- The `CN` FORMAT field contains the actual integer copy number

**Ploidy=2 (diploid):**
- Baseline CN = 2
- CN=0 → `<DEL>` with `1/1` (homozygous deletion)
- CN=1 → `<DEL>` with `0/1` (heterozygous deletion)
- CN=3 → `<DUP>` with `0/1` and `CN:3` (duplication)

### Example: Haploid Sample A0-F0-I1-R1

With `--ploidy 1`:
```
chr2   <DEL>  FOLD_CHANGE=0.22  GT:GQ  1/1:164    # Complete loss (CN=0)
chr6   <DUP>  FOLD_CHANGE=1.42  GT:GQ:CN:CNQ  0/1:0:3:56  # Triplication (CN=3)
chr9   <DUP>  FOLD_CHANGE=1.21  GT:GQ:CN:CNQ  0/1:0:3:92  # Triplication (CN=3)
```

Without `--ploidy` (defaulting to 2):
```
chr2   <DEL>  FOLD_CHANGE=0.22  GT:GQ  1/1:164    # Interpreted as homozygous del
chr3   <DEL>  FOLD_CHANGE=0.78  GT:GQ  0/1:74     # False het del (actually near-normal for haploid)
chr6   <DUP>  FOLD_CHANGE=1.42  GT:GQ:CN:CNQ  0/1:0:3:56
```

Key difference: with correct ploidy, chr3 and chr5 are no longer called as deletions (their coverage is near-normal for a haploid).

## Important Notes

1. **Always use the `CN` field** for downstream analysis rather than relying on GT encoding. CN gives the actual integer copy number.

2. **The `0/1` GT for DUP events** does not mean "heterozygous" in the SNP sense. It is the standard SV-VCF convention for representing a copy number gain.

3. **Fold change interpretation** depends on ploidy. The same log2 ratio maps to different CN values at different ploidies.

4. **Cache invalidation**: When changing `ext.args` in the config, old Nextflow cached results for `CNVKIT_EXPORT` must be cleared or the pipeline run without `-resume` to pick up the new parameter.

## Known Limitation: CN Scale Does Not Reflect Ploidy

The `cn` column in `.call.cns` always uses **cn=2 as baseline** regardless of `--ploidy`, because:
1. `cnvkit.py batch` builds a flat reference without ploidy awareness
2. The default thresholds (`-1.1,-0.25,0.2,0.7`) map log2≈0 to cn=2 for all ploidies
3. `--ploidy` only affects the overflow region (log2>0.7) and VCF export

For haploid samples: cn=2 = normal, cn=3 = duplication, cn=1 = deletion.

See `cnvkit_ploidy_cn_scale.md` for the full investigation and source code analysis.

## Files Modified

- `conf/modules/cnvkit.config` (CNVKIT_CALL and CNVKIT_EXPORT)
