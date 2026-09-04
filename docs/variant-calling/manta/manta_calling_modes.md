# Manta calling modes: which one to use

**Date**: 2026-09-03 · Evidence: [`manta_joint_at_scale/REPORT.md`](../../benchmarking/ottilie_xenobiotic_ale/04_validate/manta_joint_at_scale/REPORT.md)

Three modes were compared on the same CRAMs at three cohort sizes (4, 16 and 86 samples), scoring the
**merged SV pass table** (`sv_cohort_matrix_union_pass.csv`) — the deliverable, not intermediate VCFs.

## Use joint per-experiment Manta (the default)

`--joint_manta` (default `true`) is the right mode for a normal ALE experiment — a parent plus a few
clones. The reason is the parent:

- **Per-sample Manta makes shared background look clone-specific.** The parent's own VCF misses the
  strain's engineered cassette junctions, so every clone that calls them appears to carry a unique SV.
  Measured false clone-specific rows: **13 of 16** at 4 samples, **26 of 34** at 16 — the error *grows*
  with cohort size, because the parent's blind spot is constant while each added clone re-reports it.
- **Joint mode fixes it once, for everyone**: 3 clone-specific rows, **0 false**, at both 4 and 16
  samples — flat with cohort size.
- The SVDB merge and TIDDIT do **not** repair this. They rescue events (so row counts look similar:
  51 vs 50 at 4 samples) but cannot restore the parent's missing Manta genotypes.

## Don't use it for very large cohorts

At **86 samples** joint calling pools discovery too hard: only 34% of per-sample PASS calls survive
(74% with high sensitivity), and clone-specific calls are lost in both modes. Measured points are
4 ✓, 16 ✓, 86 ✗; the interval between 16 and 86 is unmeasured. For cohorts far beyond 16, set
`--joint_manta false` and rely on per-sample calling + the SVDB merge.

The proper fix for large cohorts — splitting discovery from genotyping, as HaplotypeCaller does with
GVCFs — is [a documented roadmap item](../sv_uniform_genotyping_roadmap.md), deliberately **not**
built: joint per-experiment Manta is good enough at the sizes ALE experiments actually run.

## `--manta_high_sensitivity` stays opt-in

The flag disables Manta's two human-WGS repeat heuristics (depth filters via `--exome`, and the
breakend-hub edge cap). It is **additive** — at 4 and 16 samples it added 14–15 pass rows and removed
none — but the additions are weak evidence:

- **none of the added rows had TIDDIT agreement** (0/14 and 0/15) — all Manta-only, with Manta's own
  safeties off;
- most are shared background or partially-shared rows, which analysts subtract against the parent anyway;
- the deliverable-level gain is only **+2 real clone-specific rows, against +1 false one**, at each size.

So it is a useful *analysis* switch — run it beside the default and treat the delta as review material,
particularly when you want the engineered-background record complete — but not a default. Note it also
costs runtime that grows with cohort size (11 → 16 min at 16 samples; 1h40m → 6h27m at 86).

**Scope of this evidence:** the judgement above comes from the 4- and 16-sample merged pass tables.
The 86-sample runs were `--tools manta` only, so they have no TIDDIT corroboration or merged table to
test. In that large-cohort regime high sensitivity in fact helps a lot — raw retention 34% → 74% — but
that is rescuing joint discovery's own suppression, in a regime where joint calling isn't recommended
anyway. Neither mode has been tested on a clean, non-engineered strain.
