# Manta calling modes: which one to use

**Date**: 2026-09-03 · Evidence: [`manta_joint_at_scale/REPORT.md`](../../benchmarking/ottilie_xenobiotic_ale/04_validate/manta_joint_at_scale/REPORT.md)

Three modes were compared on the same CRAMs at three cohort sizes (4, 16 and 86 samples), scoring the
**merged SV pass table** (`sv_cohort_matrix_union_pass.csv`) — the deliverable, not intermediate VCFs.

## Use joint per-experiment Manta (the default)

`--joint_manta` (default `true`) is the right mode for a normal ALE experiment — a parent plus a few
clones. The reason is the parent:

- **Per-sample Manta makes shared background look clone-specific.** The parent's own VCF misses the
  strain's engineered cassette junctions, so every clone that calls them appears to carry a unique SV.
  Measured false clone-specific rows: **13 of 16** at 4 samples, **28 of 34** at 16 — the error *grows*
  with cohort size, because the parent's blind spot is constant while each added clone re-reports it.
- **Joint mode fixes it once, for everyone**: 3 clone-specific rows, **0 false**, at both 4 and 16
  samples. (Flat only up to 16 — it slips to 2 at 48 and 3 at 86; see the next section.)

> **What "false" means here.** A clone-specific row is scored false when its breakpoints touch a locus
> the ABC16-Green Monster parent *must* carry — a deleted ABC transporter, the ADH1 terminator anchor,
> or a cassette component (URA3, CYC1). That is an **assumption about the strain** checked against a
> curated locus list, not verification of an individual row, and the error runs one way: an incomplete
> list scores background as genuine, never the reverse. So these are **lower bounds**. Conversely, a
> clone-specific row that is *not* false is **not a confirmed mutation** — only one not at a locus we
> know to be engineered. Full statement of the assumption, and where the list has already proved
> incomplete: [`REPORT.md`](../../benchmarking/ottilie_xenobiotic_ale/04_validate/manta_joint_at_scale/REPORT.md).
- The SVDB merge and TIDDIT do **not** repair this. They rescue events (so row counts look similar:
  51 vs 50 at 4 samples) but cannot restore the parent's missing Manta genotypes.

## Don't use it for very large cohorts

At **86 samples** joint calling pools discovery too hard: only 34% of per-sample PASS calls survive
(74% with high sensitivity), and clone-specific calls are lost in both modes.

Merged-table points are **4 ✓, 16 ✓, 48 partial, 86 ✗**. Joint default's defining property — zero
false clone-specific rows — **holds at 4 and 16, then slips to 2 at 48 and 3 at 86**, while the parent
keeps Manta support in 19 → 16 → 11 → 5 rows. By 86 that has fallen *below* per-sample (7). So the
guard is **~30–50 samples, measured**: validated to 16, eroding by 48, not recommended at 86. Past it,
set `--joint_manta false` and rely on per-sample calling + the SVDB merge — accepting that per-sample's
own error (false clone-specific rows: 13 → 28 → 33 → 36) is worse in kind, just flat in mechanism.

The proper fix for large cohorts — splitting discovery from genotyping, as HaplotypeCaller does with
GVCFs — is [a documented roadmap item](../sv_uniform_genotyping_roadmap.md), deliberately **not**
built: joint per-experiment Manta is good enough at the sizes ALE experiments actually run.

## Group by biological ancestor — and don't split an experiment to manage size

`experiment` groups samples for joint calling, and the only correct basis for it is the biology:
**one experiment per ancestral strain, each with its own parent.** A submission holding three ALE
experiments from three ancestors should be three experiments at any cohort size. Doing this first
also keeps most submissions under the sizes where joint calling degrades — so it is the first
question to settle, before anything about cohort size.

What does **not** work is splitting a *single* experiment into artificial groups to keep each one
small. Measured on the 16-sample cohort split into two groups of 8
([`compare_group_split.py`](../../benchmarking/ottilie_xenobiotic_ale/04_validate/compare_group_split.py),
2026-09-07; breakend pairs count as two rows throughout):

- **Group membership changes what Manta calls.** The `MaxDepth` filter tracks *pooled* cohort depth,
  so the same junction can PASS in one group and be filtered in another. The parentless group
  (62× pooled) passed five cassette junctions with fully resolved insert sequence; the group holding
  the parent (75× pooled) passed **none** — it called three of them and filtered all three as
  `MaxDepth`. The same precise rows are `MaxDepth` in the single-group runs at 16 and 48 samples,
  and are not called at all at 86.
- **Splitting gained 22 PASS rows and lost none** against the single 16-sample group; 14 of the 22
  are known engineered background that the single group had suppressed.
- **The parent's evidence stops at the group boundary.** A parent can be in only one group, so a
  junction called elsewhere has no parent column and scores as clone-specific. Three cassette
  junctions (6 rows) were exactly there: PASS in the parentless group, `MaxDepth` in the parent's.
  The merge cannot repair this — it unifies rows that exist, and the parent's group emitted none.

Replicating one parent into every group would fix that last point, but it does not run today
(per-sample outputs are keyed on `meta.id`, so a duplicated sample collides at `BUILD_CONTIG_CN`),
it is unmeasured, and it leaves the divergence itself untouched. It trades a visible failure for an
invisible one: results that depend on an arbitrary grouping choice.

**Consequence for reading the cohort SV matrix — compare within an experiment, not across.** Nine
engineered-background junctions (18 rows) failed to unify between the two groups, so a genuine
multi-experiment cohort should be expected to carry parallel rows for the same physical junction.
Within an experiment its own parent exculpates those rows correctly; across experiments, an absent
column may mean "filtered there", not "not present there".

More than ~30 clones sharing one ancestor remains the unsolved regime, and is what the
[uniform-genotyping roadmap](../sv_uniform_genotyping_roadmap.md) targets.

*Evidence class:* the call-level facts are **measured**, on one split of one cohort. The merge
behaviour is **inferred** — that run failed downstream at `SPLIT_JOINT_VCF` (the tier-2 CRAMs carry
`@RG SM` from the original experiment name, which a renamed experiment cannot match), so the
unification counts come from applying the merge's 1 kb proximity rule to the pre-merge VCFs rather
than from the merge itself.

## `--manta_high_sensitivity` stays opt-in

The flag disables Manta's two human-WGS repeat heuristics (depth filters via `--exome`, and the
breakend-hub edge cap). It is **additive** — at 4 and 16 samples it added 14–15 pass rows and removed
none — but the additions are weak evidence:

- **none of the added rows had TIDDIT agreement** (0/14 and 0/15) — all Manta-only, with Manta's own
  safeties off;
- most are shared background or partially-shared rows, which analysts subtract against the parent anyway;
- **none of the added clone-specific rows is an evolved mutation** (checked 2026-09-04). All three per
  cohort are engineered background or repeat artifacts: junctions between cassette components — the
  Green Monster cassette is a *GFP-URA3* fragment, so breakends land in **URA3** (V:116.2–117.0 kb)
  paired with **CYC1** (X:527 kb) — or an ~80 bp deletion in the subtelomeric Y' elements
  (YLR462W/YLR463C, XII:1065 kb). The giveaway is recurrence: the same locus pairs appear
  "clone-specific" in *different* clones in different cohorts and never in the parent, which is
  marginal evidence flickering over threshold, not independent identical mutations. **Confirmed at
  read level**: the parent carries 201 read pairs spanning the URA3 → CYC1 junction, against 215 and
  217 in the two clones the matrix calls carriers — the same junction, essentially the same evidence,
  scored present in one and absent in the other.

So it is a useful *analysis* switch — run it beside the default and treat the delta as review material,
particularly when you want the engineered-background record complete — but not a default. Note it also
costs runtime that grows with cohort size (11 → 16 min at 16 samples; 1h40m → 6h27m at 86).

**Scope of this evidence:** merged pass tables now exist at all four sizes (4, 16, 48, 86), and the
opt-in judgement survives them. High sensitivity holds the parent up as cohorts grow (Manta-supported
parent rows 30 → 28 → 22 → 16 vs default's 19 → 16 → 11 → 5) but costs false clone-specific rows at 48
(4 vs 2) and matches at 86 (3 vs 3) — so it rescues joint discovery's own suppression in a regime
where joint calling isn't recommended anyway. The TIDDIT-corroboration numbers (0/14, 0/15) are from
the 4- and 16-sample tables. Neither mode has been tested on a clean, non-engineered strain.
