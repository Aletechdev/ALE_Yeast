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
`--step variant_calling --tools manta,tiddit`). "FALSE" = a clone-specific row whose breakpoints
touch a deleted-ABC/ADH1 cassette locus, i.e. engineered background misreported as an evolved event.

**4 samples**

| Mode | Pass rows | Parent present | Clone-specific | of which FALSE | Parent via Manta |
|---|---|---|---|---|---|
| Per-sample | 51 | 35 | 16 | **13** | 7 |
| Joint, default | 50 | 47 | 3 | **0** | 19 |
| Joint, high-sens | 64 | 58 | 6 | 1 | 30 |

**16 samples**

| Mode | Pass rows | Parent present | Clone-specific | of which FALSE | Parent via Manta |
|---|---|---|---|---|---|
| Per-sample | 69 | 35 | 34 | **26** | 7 |
| Joint, default | 47 | 44 | 3 | **0** | 16 |
| Joint, high-sens | 62 | 56 | 6 | 1 | 28 |

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
   partial 4 / 9, clone-specific 3 / 3 — of which only **2 real (+1 false) per cohort**. So the
   deliverable-level gain is small and uncorroborated: an analysis switch, not a default.

### Guard threshold — revised

The earlier "~15–20 samples" caution in this report was **interpolated between 4 (good) and 86 (bad)
and is now falsified at its lower end**: at 16 samples joint mode's merged table is as clean as at 4.
Measured points are now 4 ✓, 16 ✓, 86 ✗ (raw-VCF level). Any guard must therefore sit **well above
16**, and the interval 16–86 is unmeasured — so either measure an intermediate cohort (e.g. 40) before
naming a number, or word the guidance as "validated to 16 samples; joint discovery degrades by 86"
without a hard cutoff.
