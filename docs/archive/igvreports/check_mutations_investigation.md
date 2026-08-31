# IGVReports — Archived Investigation Logs

> Archived dated investigation logs moved verbatim from `docs/igvreports/check_mutations.md`.
> These are point-in-time benchmark/POC results; the durable architecture and methodology
> remain in `docs/igvreports/check_mutations.md`.

---

## POC Results (April 2026)

### Single-sample report: validated
- **Sample**: A1-F6-I1-R1 (evolved clone)
- **Variants**: 113 (from individual_from_joint VCF)
- **Time**: ~30 seconds
- **Size**: 11 MB HTML
- **Includes**: IGV read pileups, per-sample GT/AD/DP/GQ/VAF

### Cohort table (no tracks): validated
- **Variants**: 1,748 (joint HaplotypeCaller)
- **Time**: ~10 seconds
- **Size**: 8.9 MB HTML
- **Includes**: FILTER, INFO fields, per-sample GT/AD/DP/GQ (all 17 samples)

### Full cohort with all CRAMs: NOT feasible on D4as
- **Terminated** after 1h18m, 10 GB / 12 GB RAM (83% memory)
- 17 CRAMs × 1,748 variants = too much data to embed

---

## Full Workflow Results (April 2026)

### Nextflow workflow: `generate_all_reports.nf` (superseded)
- **Runtime**: 18m 48s (37 tasks)
- **Architecture**: PREPARE_GFF3 → PREPARE_VCF (×18) → IGVREPORTS_COHORT + IGVREPORTS_SAMPLE (×17) → GENERATE_INDEX
- **Input**: SnpEff-annotated VCFs (non-hard-filtered, ~113 variants/sample)
- **Status**: Removed from repo (its commit was dropped in the 2026-08 history rewrite; see `docs/dev-practices/history_rewrite_2026-08.md`). Superseded by `generate_demo_reports.nf`.

### Output sizes
| Report | Variants | Size |
|--------|----------|------|
| Cohort (all samples, no tracks) | 7,433 | 17 MB |
| Per-sample I1 replicates | ~113 | 6–16 MB |
| Per-sample I2/I3 replicates | ~113 | 135–196 MB |

Large I2/I3 report sizes are due to higher ploidy configuration that reports lower frequency mutations.

### Columns displayed
- **INFO columns**: ANN (auto-parsed → 7 sub-columns), VCF_FILTER, AC, AF, DP, QD, MQ
- **FORMAT columns**: GT, AD, DP, GQ, VAF
