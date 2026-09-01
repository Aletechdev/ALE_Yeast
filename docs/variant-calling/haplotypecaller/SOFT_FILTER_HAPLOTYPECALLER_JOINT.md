# Soft Filter: HaplotypeCaller Joint VCF (`VARIANTFILTRATION_FALLBACK`)

## Overview

GATK VariantFiltration is applied as a **soft filter** (also called "filter annotation") on the joint HaplotypeCaller VCF. It **populates the FILTER column** with `PASS` or named filter tags but **does not remove any variants**.

This was implemented as a fallback because VQSR (Variant Quality Score Recalibration) requires known variant resources (e.g., dbSNP, HapMap) that don't exist for our custom yeast genome.

### Why a fallback is necessary (not cosmetic)

Without it, the joint VCF reaches downstream analysis with **the FILTER column unset on every record**. VQSR is what would normally populate it (plus a `VQSLOD` score); with no VQSR and no replacement, nothing does. Verified on the Ottilie Tier 2 output:

```console
$ bcftools query -f '%FILTER\n' joint_germline.vcf.gz | sort | uniq -c
   1521 .                          # ← pre-fallback: every record unset

$ bcftools query -f '%FILTER\n' HaplotypeCaller_joint_calling_soft_filtered.vcf.gz | sort | uniq -c
   1256 PASS
     99 MQ_filter
     70 SOR_filter
     45 MQ_filter;SOR_filter
     25 QD_filter
      ...                          # ← post-fallback: 1521 records, all flagged
```

Consequences of the unset column: `bcftools view -f PASS` returns **zero** records (`.` is not `PASS`), so any downstream step that selects on PASS silently yields an empty set rather than erroring. Nothing distinguishes a well-supported call from a low-quality one. The [hard filter](HARD_FILTER_HAPLOTYPECALLER_JOINT.md) also requires `FILTER=PASS` as its prerequisite, so it has nothing to act on.

Note that `QUAL` and the annotation fields (`QD`, `FS`, `SOR`, `MQ`, …) *are* present regardless — they come from HaplotypeCaller, not VQSR. That is precisely why hard-filtering on them is possible as a substitute.

### What triggers the fallback

The fallback is selected whenever `VARIANTRECALIBRATOR_*` fails to run, which happens when **either** of VQSR's two resource inputs is unsatisfied:

| VariantRecalibrator input | Supplied by | Params |
|---------------------------|-------------|--------|
| `resource_vcf` / `resource_tbi` | the resource **VCF files** | `--dbsnp`, `--known_snps`, `--known_indels` |
| `labels` | the `--resource:...` **argument strings** | `--dbsnp_vqsr`, `--known_snps_vqsr`, `--known_indels_vqsr` |

Both families are required. Supplying only the files, or only the labels, still leaves the recalibrator starved and still lands on this fallback.

Mechanism: an unset param becomes an empty channel, both input channels are built with `.collect()`, and `collect()` — which defaults to `flat: true` — **emits nothing** when the flattened result is empty. A process whose input never emits never launches, so `VARIANTRECALIBRATOR_*` and then `APPLYVQSR` are skipped; `.ifEmpty([[:], []])` yields `[]`, falsy in `recal_vcf ?: fallback_vcf`, and the fallback wins. There is no `ext.when` anywhere in the chain — the gating is purely this empty-channel propagation.

For this pipeline **all six params are null** (custom genome, no `igenomes.config` entry for `getGenomeAttribute`, nothing set in our configs), so the fallback is the only path ever taken.

> **This same starvation pattern gates BQSR and `FilterVariantTranches` too**, and `--dbsnp` behaves differently depending on which consumer receives it — it gates BaseRecalibrator and VariantRecalibrator, but *not* GenotypeGVCFs. Full explanation, including why a missing known-sites resource makes the BQSR run fail with a Nextflow join error rather than a GATK error: [haplotypecaller_workflow_analysis.md → The known-sites starvation pattern](haplotypecaller_workflow_analysis.md#4-the-known-sites-starvation-pattern-custom-genomes).

## Output File

```
output_all/variant_calling/haplotypecaller/joint_variant_calling/
    HaplotypeCaller_joint_calling_soft_filtered.vcf.gz
    HaplotypeCaller_joint_calling_soft_filtered.vcf.gz.tbi
```

## Key Concept: Cohort-Level Metrics

All filters operate on **INFO-level (cohort-wide) annotations**, not per-sample FORMAT fields. In a joint VCF with N samples:

- **INFO/DP** = total read depth summed across all samples at that site
- **QUAL** = Phred-scaled site-level quality score across all samples
- **QD** = QUAL divided by INFO/DP (quality normalized by total depth)
- **FS, SOR** = strand bias computed from all reads across all samples
- **MQ** = root mean square mapping quality across all reads at the site
- **MQRankSum, ReadPosRankSum** = rank sum tests comparing REF vs ALT reads across all samples

This means a variant can be marked `PASS` at the cohort level but still have poor quality in a specific sample. That's why the downstream [hard filter](HARD_FILTER_HAPLOTYPECALLER_JOINT.md) checks **per-sample** FORMAT fields (GQ, FORMAT/DP, FORMAT/AD).

## Filter Definitions

Filters are split by variant type per GATK best practices ([section C: SNPs, section D: INDELs](https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering)). INDELs receive fewer and more lenient filters because they naturally show more strand bias and positional bias due to alignment difficulties.

### Universal Filters (apply to both SNPs and INDELs)

| Filter Name | Expression | What It Measures |
|-------------|-----------|------------------|
| **QD_filter** | `QD < 2.0` | **Quality by Depth** — QUAL normalized by total read depth. Low QD means variant quality is not supported by sufficient evidence per read. |
| **QUAL_filter** | `QUAL < 30.0` | **Site Quality** — Phred-scaled probability of non-reference allele. QUAL < 30 means >0.1% chance the site is homozygous reference. |

### SNP-Only Filters (GATK section [C])

These use `vc.isSNP()` to restrict to SNP records only.

| Filter Name | Expression | What It Measures |
|-------------|-----------|------------------|
| **FS_filter** | `vc.isSNP() && FS > 60.0` | **Fisher Strand bias** — Phred-scaled p-value for strand bias. High FS suggests PCR or sequencing artifact. |
| **SOR_FS_filter** | `vc.isSNP() && SOR > 3.0 && FS > 0.0` | **Strand Odds Ratio, FS-gated** — Symmetric odds ratio test for strand bias, trusted only when Fisher's test also sees *some* bias. The gate is an ALE-specific deviation from GATK's plain `SOR > 3.0`; evidence in [FS-gating the SOR filter](#fs-gating-the-sor-filter-2026-09-01) below. Named `SOR_filter` before 2026-09-01. |
| **MQ_filter** | `vc.isSNP() && MQ < 40.0` | **Mapping Quality** — RMS mapping quality. Low MQ means reads map to multiple locations (repetitive region). |
| **MQRankSum_filter** | `vc.isSNP() && MQRankSum < -12.5` | **MQ Rank Sum Test** — Compares mapping quality of REF vs ALT reads. Large negative = ALT reads map poorly → mismapping artifact. |
| **ReadPosRankSum_filter** | `vc.isSNP() && ReadPosRankSum < -8.0` | **Read Position Rank Sum Test** — Compares read positions of REF vs ALT. Negative = ALT at read ends → sequencing error. |

### INDEL-Only Filters (GATK section [D])

These use `vc.isIndel()` to restrict to INDEL records only. Per GATK, INDELs do **not** receive SOR, MQ, or MQRankSum filters.

| Filter Name | Expression | Why More Lenient |
|-------------|-----------|------------------|
| **FS_INDEL_filter** | `vc.isIndel() && FS > 200.0` | INDELs cause alignment artifacts that inflate FS. Threshold is 3.3x higher than SNP (200 vs 60). |
| **ReadPosRankSum_INDEL_filter** | `vc.isIndel() && ReadPosRankSum < -20.0` | INDELs near read ends cause soft-clipping. Threshold is 2.5x more lenient than SNP (-20 vs -8). |

### Filter Application Logic

Each filter is evaluated independently. A variant can accumulate **multiple filter tags** (semicolon-delimited):

```
FILTER=PASS                          # Passes all filters
FILTER=QD_filter                     # Fails one filter
FILTER=QD_filter;FS_filter;SOR_filter  # Fails multiple filters
```

SNP-only filters (`vc.isSNP()`) are skipped for INDELs and vice versa. A SNP will never receive `FS_INDEL_filter`, and an INDEL will never receive `SOR_FS_filter`.

### Important: `TYPE==` JEXL Syntax Bug

The `TYPE==SNP` and `TYPE==INDEL` JEXL expressions **silently match nothing** in GATK VariantFiltration — they are syntactically accepted but produce zero filter hits. This was discovered during Ottilie Tier 2 validation (June 2026).

| Syntax | Result |
|--------|--------|
| `TYPE==SNP && SOR > 3.0` | 0 matches (broken) |
| `vc.isSNP() && SOR > 3.0` | 135 matches (correct) |
| `TYPE==INDEL && SOR > 3.0` | 0 matches (broken) |
| `vc.isIndel() && SOR > 3.0` | 94 matches (correct) |

**Always use `vc.isSNP()` / `vc.isIndel()`** for type-specific filtering in GATK VariantFiltration.

## Filter Performance

### Pre-fix baseline (CEN.PK 6 samples, TYPE== era — INDEL filters were no-ops)

From 1,748 total variants:

| Outcome | Count | Percentage |
|---------|-------|------------|
| **PASS** | 737 | 42.2% |
| Flagged (1+ filters) | 1,011 | 57.8% |

### Ottilie Tier 2 (86 samples, vc.isSNP()/vc.isIndel() fix)

From 1,521 total variants (823 SNPs, 698 INDELs):

| Metric | Before fix | After fix |
|--------|-----------|-----------|
| INDEL PASS rate | 514/698 (73.6%) | ~677/698 (97.0%) |
| INDELs wrongly filtered by SNP thresholds | 163 | 0 |
| Truth set sensitivity (PASS only) | 332/343 (96.8%) | 333/343 (97.1%) |

### Which filters actually fire (Ottilie Tier 2, 86 samples / 1,521 records)

> These counts predate the 2026-09-01 FS-gate ([below](#fs-gating-the-sor-filter-2026-09-01)), so the strand-bias filter appears under its old name `SOR_filter` with the plain `SOR > 3.0` expression. Under the gated rule, 30 of the 135 `SOR_filter` tags (the FS = 0 subset among SOR-only failures) are not assigned.

Nine filters are declared, and the header of the output VCF confirms all nine were passed to VariantFiltration. **Only four ever fire:**

| Filter | Records tagged |
|--------|---------------|
| `MQ_filter` | 152 |
| `SOR_filter` | 135 |
| `QD_filter` | 26 |
| `FS_filter` | 25 |

1,256 / 1,521 records (82.6%) are `PASS`. The remaining five filters tag **nothing**, and the reasons differ — this matters, because one of them can never fire at all:

| Filter | Candidates | Why |
|--------|-----------|-----|
| **`QUAL_filter` (QUAL < 30)** | 0 | **Structurally redundant.** GenotypeGVCFs' default `-stand-call-conf 30` means no record below QUAL 30 is ever emitted — observed minimum is **30.14**. This filter cannot fire on any dataset unless `stand-call-conf` is lowered. |
| `MQRankSum_filter` (< −12.5) | 0 | observed minimum **−6.97** — the human-derived threshold is far from the data |
| `ReadPosRankSum_filter` (< −8.0) | 0 | observed minimum **−4.73** |
| `FS_INDEL_filter` (FS > 200) | 0 | INDELs are present in quantity, but none approach FS 200 |
| `ReadPosRankSum_INDEL_filter` (< −20) | 0 | same |

**Annotation coverage gap.** `MQRankSum` is absent on 575 / 1,521 records and `ReadPosRankSum` on 590 / 1,521 — the RankSum statistics require both REF and ALT reads at a site, so they are undefined at sites where every sample is hom-var (common with haploid ALE strains). GATK's default treats an undefined annotation as *not failing*, so on those records the RankSum filters are silently skipped. On roughly 38% of records the effective filter set is just QD / FS / SOR / MQ.

**Net:** the working filter set is **four filters, not nine**, and the INDEL-specific half of the config contributes nothing on this dataset. This is evidence for — not against — the threshold review in [Considerations for Yeast ALE](#considerations-for-yeast-ale) below; note that `QUAL_filter` is redundant *by construction* rather than by threshold, so it needs removing or re-tying to `stand-call-conf` rather than retuning.

> Caveat when interpreting these thresholds: BQSR is skipped on custom genomes, so `QUAL`, `QD` and `MQ` are raw caller estimates rather than recalibrated ones. The GATK human thresholds were derived against recalibrated scores.

## Pipeline Position

```
GenomicsDBImport → GenotypeGVCFs → MergeVCFs (joint_germline.vcf.gz)
                                        │
                                        ├── VQSR (fails for custom genomes)
                                        │
                                        └── VARIANTFILTRATION_FALLBACK ──► soft_filtered.vcf.gz
                                                                                │
                                                     ┌──────────────────────────┘
                                                     │
                                              Split Joint VCF (--split_haplotypecaller_joint_vcf)
                                                     │
                                              Hard Filter (--hard_filter_haplotypecaller_joint)
                                              [per-sample FORMAT fields: GQ, DP, AD]
```

**Three-tier priority logic** (in workflow):
1. VQSR recalibrated VCF (when known sites available — e.g., human)
2. Filter-annotated VCF (fallback for custom genomes — our case)
3. Unfiltered VCF (should not happen — this is the all-`.` FILTER column described above)

## Sibling steps that also need known variants

VQSR is not the only GATK step that assumes a known-variants resource — BQSR and `FilterVariantTranches` are gated by the same mechanism, but only VQSR has a fallback. The other two either abort the run or are bypassed. Comparison table and failure modes: [haplotypecaller_workflow_analysis.md → The known-sites starvation pattern](haplotypecaller_workflow_analysis.md#4-the-known-sites-starvation-pattern-custom-genomes).

The one operational point worth repeating here: **BQSR is a manual opt-out**, not an automatic one. `skip_tools = 'baserecalibrator'` (`conf/test/ottilie_test.config`, and the run scripts) must be set — drop it and the run aborts.

## Configuration

**Config file**: `conf/modules/joint_germline.config`

**Workflow file**: `subworkflows/local/bam_joint_calling_germline_gatk/main.nf`

## Relationship to Hard Filter

| Aspect | Soft Filter (this doc) | [Hard Filter](HARD_FILTER_HAPLOTYPECALLER_JOINT.md) |
|--------|----------------------|-----------------------------------------------------|
| Tool | GATK VariantFiltration | bcftools filter |
| Scope | Cohort-level (INFO fields) | Per-sample (FORMAT fields) |
| Action | Tags FILTER column | Removes variants entirely |
| Input | Joint VCF (all samples) | Individual VCFs (split from joint) |
| Metrics | QD, FS, SOR, MQ, QUAL, RankSum tests | GQ, FORMAT/DP, FORMAT/AD |
| Prerequisite | None | Requires `FILTER=PASS` from soft filter |

## Extracting PASS Variants

```bash
# From joint VCF (all samples, cohort-level PASS):
bcftools view -f PASS HaplotypeCaller_joint_calling_soft_filtered.vcf.gz -O z -o joint_PASS.vcf.gz

# Count PASS vs flagged:
bcftools view -H -f PASS file.vcf.gz | wc -l    # PASS count
bcftools view -H file.vcf.gz | wc -l             # Total count
```

## Considerations for Yeast ALE

The current filter thresholds are based on **GATK best practices for human data**. Potential adjustments for yeast:

- **QD_filter (QD < 2.0)**: Most restrictive filter. Yeast has a smaller genome with higher per-base coverage; consider whether QD < 1.5 or QD < 1.0 would be more appropriate.
- **MQ_filter (MQ < 40.0)**: Yeast genome has fewer repetitive regions than human, so most reads should map uniquely (MQ=60). This filter likely catches genuine mapping issues. **Reviewed 2026-09-01 and deliberately kept at 40** — see [Why MQ_filter was left alone](#why-mq_filter-was-left-alone) below.
- **SOR/FS thresholds**: Deep ALE sequencing may amplify natural strand bias — SOR fired on real mutations that FS scored as bias-free. **Resolved 2026-09-01 by FS-gating the SOR filter** — see the next section.

These thresholds should be validated against known ALE mutation types before relaxation.

## FS-gating the SOR filter (2026-09-01)

The SNP strand-bias filter was changed from GATK's stock expression to an FS-gated one, and renamed to make the compound expression visible in the tag:

| | Before | After |
|---|---|---|
| Name | `SOR_filter` | `SOR_FS_filter` |
| Expression | `vc.isSNP() && SOR > 3.0` | `vc.isSNP() && SOR > 3.0 && FS > 0.0` |

The gate means: only trust SOR's strand-bias claim when Fisher's exact test — computed from the same reads — also sees at least *some* bias. `FS = 0` (p = 1, no bias whatsoever) alongside `SOR > 3` is the signature of SOR's known instability when one allele has very few reads on one strand, which deep clonal ALE coverage produces routinely.

### Evidence (Ottilie Tier 2 — 86 samples, 343 truth mutations, 1,521 joint records)

PASS-only sensitivity was 333/343 vs 339/343 for all records — **6 truth mutations lost purely to soft-filter tags**, 5 of them involving the SOR filter. Every SOR-lost site had high QUAL (608–1773), high QD (25–31), and **FS = 0**:

| Site | FILTER | SOR | FS | MQ |
|---|---|---|---|---|
| IV:126739 G>T (YDL185C-A) | SOR only | 3.77 | 0 | 60 |
| VIII:447631 C>T | SOR only | 3.26 | 0 | 60 |
| XVI:139634 T>G (BMS1 missense) | SOR only | 4.09 | 0 | 60 |
| XIV:572452 C>T | SOR only | 5.42 | 0 | 43.9 |
| IX:19436 C>G | SOR + MQ | 6.27 | 0 | 39.6 |

Candidate fixes were swept against the full joint VCF (rescuable = the 4 SOR-only sites; IX:19436 also fails MQ):

| Candidate | Truth rescued (of 4) | Non-truth records flipped to PASS |
|---|---|---|
| SOR > 4.0 | 2 | 36 |
| SOR > 4.5 | 3 | 44 |
| SOR > 5.5 | 4 | 54 |
| **`SOR > 3.0 && FS > 0.0`** | **4** | **30** |

The FS-gate dominates every plain threshold raise — full rescue at the lowest cost, with a mechanism (SOR instability) rather than a looser number. Expected PASS-only sensitivity: **337/343 (98.3%)**; the remaining misses are 4 caller-level and 2 justified MQ flags.

### Standing on GATK's recommendations

- The [reference article](https://gatk.broadinstitute.org/hc/en-us/articles/360035531112) states that its thresholds are generic starting values and that *"researchers are expected to fine-tune hard-filtering thresholds for their data"* by stratifying annotation distributions against a truth set — which is exactly the procedure above.
- The article warns against **compound filter expressions**: a record missing any referenced annotation auto-passes the whole expression (fail-open). This is moot here — FS and SOR are computed together and present on 1,521/1,521 Tier 2 records — and fail-open on a *soft* filter at worst leaves a record untagged. (The config already relies on compound JEXL via `vc.isSNP()`.)

### Why MQ_filter was left alone

The same sweep was run for MQ (152 records tagged, median MQ 31.8). Two truth mutations are MQ-blocked — IV:7879 (MQ 34.6) and IX:19436 (MQ 39.6) — both subtelomeric intergenic sites in repeat-family territory (the PAU6 pattern: real, but inherently ambiguous with short-read mapping). Rescuing the first costs +53 flipped records (MQ < 34), the second requires shaving the cutoff to 39.5 to catch a variant 0.41 below it — threshold-chasing with no independent witness annotation to gate on (FS plays that role for SOR; nothing equivalent exists for MQ). Both remain visible in the VCF under their tags.

### Downstream name references

Nothing in the pipeline keys on the filter-name strings (downstream logic only tests `PASS` vs non-PASS), so the rename is behavior-safe. Historical write-ups (this doc's fire counts above, `04_validate/tier2_results/`, the marko_sv dashboard) keep `SOR_filter` — they describe outputs produced under the old rule, and each VCF's `##FILTER` header records the exact expression that generated its tags.

## Verifying a filter change

After changing filter expressions, re-run the pipeline and check that each filter behaves as intended — SNP-only filters must not tag INDELs, and every declared filter should either fire or be explainable as having no candidates (see [Which filters actually fire](#which-filters-actually-fire-ottilie-tier-2-86-samples--1521-records)).

```bash
JV=output_.../joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz

# 1. Which filters fire, and how often
bcftools query -f '%FILTER\n' "$JV" | tr ';' '\n' | sort | uniq -c | sort -rn

# 2. Every declared filter (compare against 1 — anything absent never fired)
bcftools view -h "$JV" | grep '^##FILTER' | sed 's/,Description.*//'

# 3. PASS rate by variant type
for t in snps indels; do
  tot=$(bcftools view -H -v $t "$JV" | wc -l)
  pas=$(bcftools view -H -v $t -f PASS "$JV" | wc -l)
  awk -v t=$t -v a=$tot -v p=$pas 'BEGIN{printf "%-7s %d/%d PASS (%.1f%%)\n", t, p, a, 100*p/a}'
done

# 4. Leakage check: INDELs must never carry a SNP-only filter
bcftools view -H -v indels -i 'FILTER~"SOR_FS_filter" || FILTER~"MQ_filter" || FILTER~"FS_filter"' "$JV" | wc -l   # expect 0

# 5. Is an annotation even present? (a filter on a missing field silently never fires)
bcftools query -f '%INFO/MQRankSum\n' "$JV" | grep -vc '^\.$'
```

Check 4 is the regression guard for the `TYPE==` class of bug: a JEXL expression that silently matches nothing produces an all-PASS result that looks healthy. Check 5 covers the complementary case — GATK treats an undefined annotation as *not failing*, so a filter on an absent field is inert rather than erroring.
