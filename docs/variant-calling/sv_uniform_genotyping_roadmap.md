# Roadmap: uniform SV genotyping (a GVCF-style architecture for SVs)

**Status: post-1.0 roadmap item, not scheduled.** Nothing here is implemented. Recorded 2026-09-03
so the rationale and the evidence behind it survive; see "When to promote this" for the trigger.

## The problem it solves

For SNVs, HaplotypeCaller gives **uniform genotypes** — every sample is assessed at every cohort
site, so `0/0` means "looked, and absent", not "never asked". That is the whole reason the ALE
pipeline runs joint germline calling. For SVs the pipeline has no equivalent guarantee:

- **Per-sample Manta**: each VCF lists only the sites that sample discovered. Absence is ambiguous,
  and the ambiguity is not neutral — it manufactures false clone-specificity when the *parent* is the
  sample that misses a shared junction (measured: 13 of 16 clone-specific rows false at 4 samples,
  26 of 34 at 16 — and the error grows with cohort size).
- **Joint Manta** (`--joint_manta`, the current default) fixes that by pooling *discovery*, which is
  where its cost lives: at 86 samples it retains only 34% of per-sample PASS calls (74% with
  `--manta_high_sensitivity`) and destroys clone-specific calls that no flag recovers.

Evidence for both: [`04_validate/manta_joint_at_scale/REPORT.md`](../benchmarking/ottilie_xenobiotic_ale/04_validate/manta_joint_at_scale/REPORT.md)
and [`pilot_results_v2/NOTES.md`](../benchmarking/ottilie_xenobiotic_ale/04_validate/pilot_results_v2/NOTES.md).

## The architecture

Mirror what HC does with GVCFs — **separate discovery from genotyping**, which Manta cannot do alone
(it has no genotype-only mode, so for Manta "joint" necessarily means "pooled discovery"):

| Step | HC analogue | SV implementation |
|---|---|---|
| 1. Per-sample discovery | HaplotypeCaller → GVCF | Per-sample Manta + TIDDIT (already in the pipeline; sensitive, parallel, no pooling) |
| 2. Cohort candidate union | GenomicsDBImport | SVDB merge (already in the pipeline) |
| 3. Force-genotype every sample at every site | GenotypeGVCFs | **Missing piece**: a dedicated SV genotyper |

Result: uniform genotypes at any cohort size, without joint discovery's suppression, and every step
stays parallel (step 3 is per-sample again). The pipeline is already two-thirds of this.

## Design constraints learned from the 2026-09 experiments

1. **Discovery must run with Manta's depth filters off.** The engineered cassette junctions sit above
   Manta's collapsed-repeat depth threshold; stock settings tag or drop them. This applies to the
   *per-sample* discovery leg here, not just to joint mode — see `--manta_high_sensitivity`.
2. **The genotyper must handle breakends (BND) well.** The dominant real structure in this data is a
   multi-copy cassette breakend star (see [`DATA_PROVENANCE`](../benchmarking/ottilie_xenobiotic_ale/DATA_PROVENANCE.md)
   and the ADH1-terminator/U1-UPTAG-U2 proof). Graph-based genotypers (Paragraph, GraphTyper2) suit
   this; `delly call -v sites.bcf` is weakest exactly on BNDs.
3. **Haploid/clonal samples**: every candidate genotyper must be checked against `ploidy = 1` ALE
   data — none of them is validated for that here.
4. **It would also retire the `-`-vs-absent ambiguity** in `sv_cohort_matrix_union_pass.csv`, which is
   currently an analyst-level judgement against the parent column (the pipeline does **no** parent
   subtraction for SVs).

## When to promote this

Not now: joint per-experiment Manta is measured clean at 4 and 16 samples, which covers a normal ALE
experiment (a parent plus a few clones). Promote it when either becomes true:

- real campaigns routinely put **≳30 clones in one `experiment`** (Tier-2's 86 samples is a real
  dataset, so this is not hypothetical); or
- a bracketing run (~40 samples) shows joint discovery's knee is **closer to 16 than assumed** — the
  16–86 interval is currently unmeasured.

Until then the guidance is: joint per-experiment Manta, paired with `--manta_high_sensitivity` for
engineered backgrounds, and per-sample + SVDB merge as the fallback for oversized cohorts.
