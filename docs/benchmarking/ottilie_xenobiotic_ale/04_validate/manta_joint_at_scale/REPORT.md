# Joint Manta at 86 samples — call-quality and resource report

**Date**: 2026-09-01 · **Pipeline**: commit `4c45fb8` · **Author**: audit run by Claude Code session

## Question

Item (D) of the Seqera launch-form plan proposes changing `--joint_manta` grouping from
per-experiment to **all germline samples**. The 86-sample Tier-2 cohort is the worst case that
grouping would create. Two questions: does it run on the dev VM, and are the calls still good?

## Setup

One joint `MANTA_GERMLINE` call over all 86 Tier-2 `md.cram`s (one `experiment` = `Ottilie_tier2`),
`--step variant_calling --tools manta --joint_manta`, dev VM (4 vCPU / 16 GB):

- Joint output: `output_manta_joint_test/variant_calling/manta/` (joint VCF + 86 split per-sample VCFs)
- Per-sample baseline: `output_ottilie_tier2/variant_calling/manta/<sample>/` — **same CRAMs**
- Audit tool: [`manta_joint_vs_single.py`](../manta_joint_vs_single.py) → `summary.tsv` (committed) plus
  per-sample `details_<sample>.tsv` (not committed — regenerate by re-running the tool)

## Resource verdict: runs, after an fd-limit fix

| Constraint | Result |
|---|---|
| File descriptors | **Hard failure at defaults**: `GenerateSVCandidates` opens all CRAMs per thread (86 × 4 × ~3 ≈ 1,030 handles) vs container soft ulimit 1024 → deterministic `Too many open files` FATAL. Fix verified: `docker.runOptions` + `--ulimit nofile=65536:65536`. Cliff ≈ 80 samples at defaults. |
| Wall-clock | 1h 40m for the single serialized task (368% CPU) vs ~3 min for a 4-sample joint call. |
| Memory | **Trivial**: peak_rss 3 GB of 8 GB allocated. ~1.8 GiB plateau through depth + locus graph (streams region-by-region; graph bounded by the 12 Mb genome), bump to 3 GB in candidate generation/genotyping. |

## Call-quality verdict: severe suppression — joint-at-86 is not usable

The joint VCF contains **27 records for the entire cohort**, vs 1,543 records (1,149 PASS) across
the 86 per-sample VCFs. Per-sample PASS retention in the joint output: **392 / 1,149 = 34.1%**
(757 PASS calls lost). Losses include maximal-evidence calls, e.g. NODRUG-GM2 III:84801 DEL,
GT 1/1, GQ 204, PR/SR 43/40 — absent from the joint VCF entirely.

Sharing structure of the 757 lost PASS record-instances (grouped into 87 distinct loci):

| Category | Loci | Lost record-instances |
|---|---|---|
| Shared background (locus in ≥10 samples) | 17 | 527 |
| Intermediate (3–9 samples) | 25 | 169 |
| **Private (≤2 samples)** | **45** | **61** |

- The bulk is cohort-shared strain background (a DEL present in all 86 samples, another in 85/86,
  the XV:159kb ADH1-region breakend cluster, …) — consistent with pooled-graph complexity caps
  (`--max-edge-count 10`) and pooled-depth heuristics collapsing junctions every sample carries.
  Note the pipeline performs **no parent subtraction for SVs** — the parent (NODRUG-GM2, present
  in this joint run as an ordinary sample) is just another column in the cohort matrix, and
  background-vs-clone-specific is an analyst-level comparison against the parent's row. Uniform
  loss (all samples incl. the parent, e.g. the 86/86 DEL) at least fabricates no false
  clone-specific signal, but it silently erases the engineered-background record (ADH1 star,
  cassette junctions) from the deliverable — and joint mode does not guarantee uniformity.
  **Non-uniform loss is observed, not hypothetical**: 4 loci have mixed outcomes, worst being the
  ADH1-region breakend cluster (XV:159.6–159.7kb) — kept in the joint output for ~21–26 samples,
  lost for ~19–23, parent absent per-sample (the known parent blind spot) — so an engineered locus
  carried by every sample renders as a *partially shared* SV in the cohort matrix.
- **The disqualifying category is the 61 private losses across 45 loci**: clone-specific SV calls —
  the actual ALE deliverable — vanish in joint mode (e.g. CHX--Cy73-2 Mito BNDs, CBR113--1-R4a
  III/XII/XV BNDs, PMA1--D1 XVI:450300).
- Joint mode's benefit axis barely registers at this scale: 136 joint-only genotype presences
  cohort-wide, against 757 lost PASS calls.

This matches Manta's own small-cohort guidance for joint diploid calling and inverts the 4-sample
result (where joint mode *added* evidence-backed genotypes with no corroborated losses — see
`../manta_joint_audit/`, `pilot_results_v2/NOTES.md`).

## High-sensitivity rerun (2026-09-02): rescues the background, not the private calls

The 4-sample audit proved the two dominant joint-mode loss mechanisms are the pooled-depth discovery
skip and the breakend-hub edge cap — both disabled by `--manta_high_sensitivity`. The same 86-sample
joint call was rerun with that flag (`output_manta_joint_test_hs/`, resumed session, audit in
`../manta_joint_at_scale_hs/`):

| Metric (86 samples) | Default joint | High-sensitivity joint |
|---|---|---|
| Joint records (PASS) | 27 (23) | 68 (47) |
| Per-sample PASS retention | 392/1,149 (34.1%) | 851/1,149 (**74.1%**) |
| PASS record-instances lost | 757 | 298 |
| … from shared (≥10-sample) loci | 527 | 112 |
| … from **private (≤2-sample) loci** | 61 (45 loci) | **56 (41 loci — 41/45 the same)** |
| Joint-only genotype presences | 136 | 610 |
| Non-uniform (mixed-outcome) loci | 4 | 4 (ADH1 cluster still split ~24 kept / ~14 lost) |
| MANTA_GERMLINE peak_rss / runtime | 3 GB / 1h 40m | 3.2 GB / **6h 27m** |

Interpretation:
- High sensitivity does what it was built for: the shared engineered background comes back
  (527 → 112 shared-locus losses) and the joint-genotyping benefit scales (610 joint-only
  presences). The depth-skip mechanism explains most of the default-mode collapse.
- **It does not rescue clone-specific calls**: 41 of the 45 private lost loci are lost in both
  modes. Whatever suppresses them (joint diploid-model consensus/scoring across 86 near-hom-ref
  samples, not the depth or edge heuristics), it is not switchable off. The ALE deliverable —
  per-clone SVs — still silently loses ~56 calls.
- The non-uniform ADH1 split persists, so the misleading partially-shared rendering is not fixed.
- Cost: one 6.5 h serialized task (memory stays modest — the interim ~6.8 GiB docker reading was
  page cache; true peak_rss 3.2 GB).

**The negative verdict on unconditional all-samples grouping therefore stands in both modes**, now
with the mechanism split: depth heuristics caused the bulk losses (fixable), joint scoring at scale
causes the private-call losses (not fixable by any exposed knob).

## Implication for item (D)

**All-samples grouping is unsafe as an unconditional default.** Between 4 samples (net benefit)
and 86 samples (34% retention, private-call loss) the quality collapses somewhere; this test does
not locate the knee. Options, in decreasing conservatism:

1. Keep per-experiment grouping (status quo); document the cohort-size caveat in the help text.
2. All-samples grouping only under a sample-count guard, falling back to per-sample + SVDB merge.
   ⚠️ The "~15–20" figure first drafted here is **falsified** — see
   [Guard threshold — revised](#guard-threshold--revised): joint mode's merged table is clean at 16.
3. If (D) proceeds in any form, it must ship the fd ulimit raise (`nextflow.config` docker
   profiles + Azure Batch equivalent) — required above ~80 samples regardless of grouping,
   and harmless otherwise.

The per-sample + SVDB-merge path remains the scale-safe architecture: it already delivers cohort
matrices, and its losses are visible (soft-filtered) rather than silent.

## The merged SV pass table — what users actually read (2026-09-03)

The audits above compare raw Manta VCFs. This section compares the **deliverable**: the SVDB-merged,
TIDDIT-corroborated `sv_cohort_matrix_union_pass.csv`. Three Manta modes were run through the full
chain at two cohort sizes (4-sample pilot; 16 samples = parent + 15 clones from the Tier-2 CRAMs,
`--step variant_calling --tools manta,tiddit`). "FALSE" = a clone-specific row whose breakpoints touch
an engineered locus the parent must also carry — a deleted ABC transporter, or a cassette component
(ADH1 terminator, URA3 marker, CYC1) — i.e. background misreported as an evolved event. Reproduce with
[`compare_sv_pass_tables.py`](../compare_sv_pass_tables.py); pipeline runs by
[`run_sv_mode_series.sh`](../run_sv_mode_series.sh). Counts here include URA3/CYC1; a first revision
of this table omitted them and read 1 lower for high-sens and 2 lower for per-sample at 16 samples.

**4 samples**

| Mode | Pass rows | Parent present | Clone-specific | of which FALSE | Parent via Manta |
|---|---|---|---|---|---|
| Per-sample | 51 | 35 | 16 | **13** | 7 |
| Joint, default | 50 | 47 | 3 | **0** | 19 |
| Joint, high-sens | 64 | 58 | 6 | 2 | 30 |

**16 samples**

| Mode | Pass rows | Parent present | Clone-specific | of which FALSE | Parent via Manta |
|---|---|---|---|---|---|
| Per-sample | 69 | 35 | 34 | **28** | 7 |
| Joint, default | 47 | 44 | 3 | **0** | 16 |
| Joint, high-sens | 62 | 56 | 6 | 2 | 28 |

**48 samples** (added 2026-09-07)

| Mode | Pass rows | Parent present | Clone-specific | of which FALSE | Parent via Manta |
|---|---|---|---|---|---|
| Per-sample | 154 | 35 | 119 | **33** | 7 |
| Joint, default | 127 | 41 | 86 | **2** | 11 |
| Joint, high-sens | 141 | 51 | 90 | 4 | 22 |

**86 samples** (added 2026-09-07)

| Mode | Pass rows | Parent present | Clone-specific | of which FALSE | Parent via Manta |
|---|---|---|---|---|---|
| Per-sample | 275 | 35 | 240 | **36** | 7 |
| Joint, default | 233 | 35 | 198 | **3** | 5 |
| Joint, high-sens | 245 | 44 | 201 | 3 | 16 |

⚠️ Clone-specific *totals* are not comparable across sizes — they scale with clone count. The
size-comparable columns are **parent present**, **parent via Manta**, and **FALSE**.

Reading the four sizes together (4 / 16 / 48 / 86):

- **Per-sample fails identically at every size and gets louder**: parent via Manta is **7 at all four
  sizes**, and FALSE grows 13 → 28 → 33 → 36. The parent's blind spot is constant; each added clone
  re-reports it.
- **Joint default degrades**: parent via Manta 19 → 16 → 11 → 5, and — the finding that moves the
  guard — **FALSE is no longer 0 past 16**: 0 → 0 → **2** → **3**. Joint's one clean property does not
  survive to 48. By 86 its parent-Manta support (5) has fallen *below* per-sample's (7).
- **High sensitivity holds the parent up** (30 → 28 → 22 → 16) but costs FALSE at 48 (4 vs 2). Since
  joint is not recommended at these sizes anyway, this does not change the opt-in decision.

Findings:

1. **Row counts hide the difference; the genotypes are the story.** At 4 samples per-sample (51) and
   joint default (50) look equivalent, yet 13 of per-sample's 16 clone-specific rows are cassette
   junctions the parent failed to call (SNQ2, YCF1 ×2, PDR15, YOR1, VMR1, PDR11, NFT1, YBT1 + four
   ADH1-anchored). The SVDB merge and TIDDIT do **not** repair this: TIDDIT rescues some events
   (which is why counts converge) but cannot restore the parent's Manta genotypes.
2. **Per-sample mode's false specificity GROWS with cohort size** — 13 → 26 false rows from 4 → 16
   samples, because each added clone independently re-reports the junctions the parent misses, while
   the parent's own Manta support stays pinned at 7 rows at both sizes.
3. **Joint mode is FLAT from 4 → 16 samples**: 3 clone-specific / 0 false (default) and 6 / 1
   (high-sens) at *both* sizes. No degradation of the deliverable at 16.
4. **High sensitivity is additive but weakly evidenced.** It adds 15 rows over default at 16 samples
   with **zero** rows lost (14 / 0 at 4 samples), and the parent gains Manta support (16 → 28 rows).
   But **none of the added rows has TIDDIT agreement** (0/14 and 0/15 — all Manta-only, with Manta's
   own heuristics disabled), and most are background or partially-shared rows that get subtracted
   against the parent anyway. Breakdown of the additions (4-sample / 16-sample): all-samples 7 / 3,
   partial 4 / 9, clone-specific 3 / 3. **Follow-up 2026-09-04: none of those clone-specific rows is
   an evolved mutation.** They are cassette-component junctions (URA3 × CYC1 — the Green Monster
   cassette is a *GFP-URA3* fragment) or a subtelomeric Y'-element deletion (XII:1065 kb), identified
   by recurrence: the same locus pairs are "clone-specific" in *different* clones across the two
   cohorts and never in the parent. An earlier version of this report called 2 of them "real"; that
   used a cassette test covering only the 16 ABC transporters and ADH1, which missed URA3 and CYC1.
   So the deliverable-level gain of high sensitivity is **zero real clone-specific calls** — it adds
   background completeness only. An analysis switch, not a default.

### Caveat: cohort size and clone diversity are confounded (2026-09-07)

The cohorts are the parent plus the first N−1 clones **in alphabetical order**
(`make_cohort_samplesheet.py`), which is deterministic but not neutral. Clone names begin with their
compound, so alphabetical selection clusters by compound: the 16-sample cohort holds 6 CBR668, 3
CBR868, 2 CBR113 and 2 CBR110 clones — 13 of 15 from four selections — while distinct compounds rise
with cohort size (7 at 16 samples, 26 at 48, 43 at 86). **So this series varies diversity as well as
size**, and the degradation curve (parent-Manta support 19 → 16 → 11 → 5) cannot cleanly separate
"more samples" from "more distinct SV candidates competing in the pooled graph".

What this does and does not touch:

- **Unaffected** — the cassette-row and parent-coverage findings. Cassette junctions are strain
  background carried by every clone whatever its compound, and per-sample mode's *parent on zero
  cassette rows at every size* does not depend on which clones surround it.
- **Weakened** — the clone-specific counts (already flagged as not size-comparable; at 16 samples
  they are further skewed by six clones sharing one compound, which by design share mutations).
- **Confounded** — the degradation curve itself. Direction almost certainly right; attribution to
  size alone is *inferred*, not measured.

The controlled test is cheap (TIDDIT for all 86 is cached): a diversity-matched 16-sample cohort —
one clone from each of 15 different compounds — needs only Manta plus the merge. If it reproduces the
single-group 16-sample result (47 rows, parent on 10/10 cassette rows, 0 false) the size reading
holds; if it looks like the 48-sample result, diversity was doing the work. **Not yet run.**

### Guard threshold — revised

The earlier "~15–20 samples" caution in this report was **interpolated between 4 (good) and 86 (bad)
and is now falsified at its lower end**: at 16 samples joint mode's merged table is as clean as at 4.
**Resolved 2026-09-07 — the intermediate cohort was measured.** Merged-table points are now
4 ✓, 16 ✓, **48 partial**, 86 ✗. Joint default holds 0 FALSE at 4 and 16, slips to 2 at 48 and 3 at
86, while its parent-Manta support decays 19 → 16 → 11 → 5. So the degradation starts *between 16 and
48* and is complete by 86: **the guard is ~30–50, now measured rather than interpolated.** Wording to
use: joint per-experiment is validated to 16, eroding by 48, and not recommended at 86.

Caveat unchanged: size and clone diversity co-vary in this series (see above), so attributing the
erosion to sample count alone remains *inferred*.

### Multi-experiment: splitting one cohort into two groups (2026-09-07)

Run: 16 tier-2 samples split into `Ottilie_grpA` (parent NODRUG-GM2 + 7 clones) and `Ottilie_grpB`
(8 clones, parentless), `--joint_manta`, high sensitivity off — the same params as the single-group
16-sample run, so **cohort membership is the only variable**. Samplesheet:
[`samplesheet_2groups_v2.csv`](samplesheet_2groups_v2.csv); scoring:
[`compare_group_split.py`](../compare_group_split.py). Breakend pairs count as two rows below.

**The run failed downstream** at `SPLIT_JOINT_VCF_MANTA`: the split names samples
`<patient>_<sample>`, correct for a from-FASTQ run, but the tier-2 CRAMs carry
`@RG SM=Ottilie_tier2_*` burned in under the original experiment name. Any run that renames the
experiment while reusing these CRAMs hits this — a constraint of CRAM reuse, **not a pipeline
defect**. (It is also the error that removing `--force-samples` in `6656c50` was meant to expose;
previously it would have emitted a sample-less VCF.) Both joint Manta calls completed first, so the
calling question is answerable from the pre-merge VCFs; **merge behaviour is inferred**, by applying
the matrix's 1 kb both-breakpoints rule to those VCFs.

| | grpA (8, parent present) | grpB (8, parentless) | single group (16) |
|---|---|---|---|
| records / PASS | 38 / 30 | 43 / 41 | 37 / 28 |
| engineered-locus PASS | 21 | 27 | — |
| cassette junctions with resolved insert | **0 PASS, 3 `MaxDepth`** | **5 PASS, 0 filtered** | 0 PASS, 3 `MaxDepth` |
| parent on engineered PASS rows | 21/21 | n/a | 10/10 (merged table) |
| pooled mean coverage | 75× | 62× | 69× |

Findings:

1. **Membership changes what is called.** grpB passed five fully insert-resolved cassette junctions;
   grpA called three of the same and filtered all three as `MaxDepth`. Across the single-group series
   the precise cassette rows are `MaxDepth` at 16 and 48 and absent at 86 — grpB is the *only*
   configuration in the whole series where they survive, and it is the lowest-depth group. Mechanism
   (`MaxDepth` tracking pooled cohort depth) is **plausible but unverified**; the divergence itself is
   measured.
2. **Splitting is additive, not lossy**: 22 PASS rows appear that the single group never called, 0
   are lost. 14 of the 22 are engineered background the single group had suppressed. Of the 8 scored
   "candidate real", 6 form a second breakend star at V:117.1 kb and a pair anchored ~300 bp from the
   cassette anchor — same architecture as known background, so 8 is an **upper bound**, not a count
   of mutations, and the engineered-locus list in the script is probably still too narrow.
3. **Parent evidence stops at the group boundary.** Three cassette junctions (6 rows) PASS in grpB
   and are `MaxDepth` in grpA. Since the parent exists only in grpA, a merged table would carry them
   with the parent absent → scored clone-specific. The single 16-sample group has no such rows
   (0 false). **Artificial splitting manufactures a false-positive class.**
4. **Cross-group unification is partial**: 9 engineered junctions (18 rows — 12 grpB-only, 6
   grpA-only) have no counterpart within 1 kb in the other group, so a real multi-experiment cohort
   should be expected to carry parallel rows for one physical junction.

**Conclusion.** Group by biological ancestor, always — that is what `experiment` means, and real
multi-experiment cohorts (each with its own parent) are fine. Do **not** split one experiment to
manage cohort size. Replicating a single parent into every group would fix finding 3 but does not
run today (per-sample publishes are keyed on `meta.id`; a duplicated sample collides at
`BUILD_CONTIG_CN` on `NODRUG-GM2.tiddit.ploidies.tab`), is unmeasured, and leaves findings 1 and 4
untouched. Guidance written up in
[`manta_calling_modes.md`](../../../../variant-calling/manta/manta_calling_modes.md).
